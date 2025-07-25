# main_integrated.py - 点检数据异常检测系统 - 优化版本
import cx_Oracle
import pandas as pd
from datetime import date, timedelta, datetime
import sys
import time as pytime
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import logging
import json
import os
import urllib.parse
from scipy import stats

# ====================================================================
# 配置区域 - Configuration Section
# ====================================================================
CONFIG = {
    'database': {
        'user': "plc",
        'password': "l5plc",
        'host': "172.18.80.23",
        'service': "orcl",
        'target_table': "TB_BARCODE_RESULT"
    },
    'model': {
        'min_data_points': 30,  # 最少数据点要求
        'lookback_window': 30,  # 回望窗口
        'optimize_interval': 20,  # 参数优化间隔
        'confidence_level': 3,  # 置信区间z值 (99%置信度)
        'holt_winters': {
            'alpha': 0.3,  # 平滑系统
            'beta': 0.1   # 趋势系数
        },
        'cox_stuart': {
            'window_size': 14,  # Cox-Stuart检验窗口大小
            'p_threshold': 0.05,  # 显著性检验阈值
            'check_interval': 14  # 检验间隔
        },
        'anomaly_replacement': {
            'consecutive_threshold': 6,  # 连续异常阈值
            'enable_replacement': True   # 是否启用异常值替换
        }
    },
    'execution': {
        'run_mode': 'FULL',  # FULL, DAILY, PREDICTION_ONLY, DETECTION_ONLY
        'stage_mode': 'BOTH',  # BOTH, PREDICTION_ONLY, DETECTION_ONLY
        'full_mode_start_date': '2025-03-01',
        'full_mode_end_date': '2025-07-18',
        'daily_days_back': 89,
        'training_history_days': 90,  # 预测训练用的历史数据天数
        'target_departments': None  # 设置为None则处理所有部门
    },
    'logging': {
        'log_level': 'INFO',
        'log_file': 'logs/anomaly_detection.log',
        'progress_file': 'logs/progress.json',
        'enable_console': True
    },
    'data_schema': {
        'required_columns': ['ANOMALY_RK', 'RESULT', 'TIME', 'MAC', 'ITEMRK', 'EMP_NAME'],
        'prediction_columns': ['PREDICTED_VALUE', 'PREDICTED_LOWER', 'PREDICTED_UPPER'],
        'anomaly_columns': ['IS_SPEC_ANOMALY', 'IS_FLUCT_ANOMALY']
    }
}

# ====================================================================
# 日志配置 - Logging Setup
# ====================================================================
def setup_logging():
    """设置日志配置"""
    log_config = CONFIG['logging']
    # 创建日志目录
    log_dir = os.path.dirname(log_config['log_file'])
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 配置日志格式
    log_format = '%(asctime)s - %(levelname)s - %(message)s'

    # 配置日志处理器
    handlers = []
    # 文件处理器
    file_handler = logging.FileHandler(log_config['log_file'], encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(file_handler)

    # 控制台处理器
    if log_config['enable_console']:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(console_handler)

    # 配置根日志记录器
    logging.basicConfig(
        level=getattr(logging, log_config['log_level']),
        handlers=handlers,
        format=log_format
    )
    return logging.getLogger(__name__)

def update_progress(stage, department=None, status='running', progress=0, message='', error=None):
    """更新运行进度到JSON文件"""
    progress_file = CONFIG['logging']['progress_file']
    # 创建进度目录
    progress_dir = os.path.dirname(progress_file)
    if progress_dir and not os.path.exists(progress_dir):
        os.makedirs(progress_dir)

    progress_data = {
        'timestamp': datetime.now().isoformat(),
        'stage': stage,
        'department': department,
        'status': status,  # running, completed, failed
        'progress': progress,
        'message': message,
        'error': str(error) if error else None
    }

    try:
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Failed to update progress file: {e}")

def check_stop_flag():
    """检查停止标志文件"""
    stop_flag_file = "logs/stop_flag.txt"
    return os.path.exists(stop_flag_file)

def clean_numeric_data(value):
    """清理数值数据，处理URL编码等问题"""
    if pd.isna(value):
        return np.nan
    # 转换为字符串
    str_value = str(value).strip()
    # URL解码
    try:
        decoded_value = urllib.parse.unquote(str_value)
    except:
        decoded_value = str_value
    # 尝试转换为浮点数
    try:
        return float(decoded_value)
    except:
        return np.nan

def cox_stuart_test(data):
    """Cox-Stuart趋势检验
    
    Args:
        data: 时间序列数据
        
    Returns:
        p_value: 检验的p值
    """
    n = len(data)
    if n < 14:
        return np.nan
    
    split_point = n // 2
    D = data[:split_point] - data[n-split_point:]
    
    s_plus = np.sum(D > 0)
    s_minus = np.sum(D < 0)
    
    k = min(s_plus, s_minus)
    n_valid = s_plus + s_minus
    
    if n_valid == 0:
        return 1.0
    
    # 使用二项分布计算p值
    p_value = stats.binom.cdf(k, n_valid, 0.5)
    return p_value

# ====================================================================
# 工具函数 - Utility Functions
# ====================================================================
def handle_exception(func):
    """异常处理装饰器"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"ERROR in {func.__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False
    return wrapper

def ensure_datetime(df, col):
    """确保列是datetime类型"""
    df[col] = pd.to_datetime(df[col], errors='coerce')
    return df

def validate_dataframe(df, required_columns):
    """验证DataFrame包含所有必需列"""
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")
    return True

# ====================================================================
# 数据库操作 - Database Operations
# ====================================================================
class DatabaseManager:
    def __init__(self, config):
        self.config = config
        self.connection = None

    def connect(self):
        """建立数据库连接"""
        try:
            db_config = self.config['database']
            connection_string = f"{db_config['user']}/{db_config['password']}@{db_config['host']}/{db_config['service']}"
            self.connection = cx_Oracle.connect(connection_string, threaded=True, events=True)
            print("Database connection successful.")
            return True
        except Exception as e:
            print(f"ERROR: Database connection failed: {e}")
            return False

    def disconnect(self):
        """断开数据库连接"""
        if self.connection:
            try:
                self.connection.close()
                print("Database connection closed.")
            except Exception as e:
                print(f"WARNING: Error closing database connection: {e}")

    def is_alive(self):
        """检查连接是否活跃"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            cursor.close()
            return True
        except:
            return False

    def fetch_data(self, sql, params=None):
        """执行查询并返回DataFrame"""
        try:
            df = pd.read_sql(sql, self.connection, params=params)
            df.columns = [col.upper() for col in df.columns]
            return df
        except Exception as e:
            print(f"ERROR: Database query failed: {e}")
            return pd.DataFrame()

    def batch_update(self, sql, data, batch_size=10000):
        """批量更新数据"""
        try:
            cursor = self.connection.cursor()
            total_affected = 0
            for i in range(0, len(data), batch_size):
                batch = data[i:i+batch_size]
                cursor.executemany(sql, batch)
                total_affected += cursor.rowcount
                self.connection.commit()
                print(f"  Batch updated: {len(batch)} records")
            cursor.close()
            return total_affected
        except Exception as e:
            print(f"ERROR: Batch update failed: {e}")
            self.connection.rollback()
            return -1

# ====================================================================
# 数据处理 - Data Processing
# ====================================================================
class DataProcessor:
    def __init__(self, config):
        self.config = config

    def fetch_source_data(self, db_manager, start_date, end_date, dept_filter=None):
        """从数据库获取源数据"""
        print(f"Target detection period: {start_date} to {end_date}")

        # 扩展查询范围以包含历史数据
        target_start_date = datetime.strptime(start_date, '%Y-%m-%d')
        training_days = self.config['execution']['training_history_days']
        extended_start_date = target_start_date - timedelta(days=training_days)
        extended_start_str = extended_start_date.strftime('%Y-%m-%d')
        print(f"Extended query range: {extended_start_str} to {end_date}")

        # 构建筛选条件
        filter_conditions = []
        if dept_filter:
            filter_conditions.append(f"EMP_NAME LIKE '%{dept_filter}%'")

        where_conditions = ""
        if filter_conditions:
            where_conditions = " AND " + " AND ".join(filter_conditions)

        sql = f"""
        SELECT MAC, ITEMNAME, ITEMRK, TIME, RESULT, CHECKDATE, ANOMALY_RK, IS_FLUCT_ANOMALY, EMP_NAME
        FROM TB_BARCODE_RESULT
        WHERE CHECKDATE BETWEEN TO_DATE(:start_dt, 'YYYY-MM-DD') AND TO_DATE(:end_dt, 'YYYY-MM-DD')
        AND RESULT IS NOT NULL
        {where_conditions}
        ORDER BY MAC, ITEMRK, TIME
        """

        df = db_manager.fetch_data(sql, {'start_dt': extended_start_str, 'end_dt': end_date})
        if df.empty:
            return df

        # 数据预处理
        df = self.process_data_interpolation(df)

        # 添加目标期间标记
        target_start_dt = pd.to_datetime(start_date)
        target_end_dt = pd.to_datetime(end_date)
        df['IS_TARGET_PERIOD'] = (df['TIME'] >= target_start_dt) & (df['TIME'] <= target_end_dt)

        print(f"Fetched {len(df)} records (target: {df['IS_TARGET_PERIOD'].sum()}, training: {len(df) - df['IS_TARGET_PERIOD'].sum()})")
        return df

    def process_data_interpolation(self, df):
        """处理数据插值，将非数值和空值进行插值处理"""
        if df.empty:
            return df

        processed_groups = []
        # 按MAC-ITEMRK分组处理
        for (mac, itemrk), group in df.groupby(['MAC', 'ITEMRK']):
            group = group.sort_values('TIME').copy()

            # 转换RESULT为数值，非数值变为NaN
            group['RESULT'] = pd.to_numeric(group['RESULT'], errors='coerce')

            # 处理缺失值
            if group['RESULT'].isna().any():
                # 使用线性插值填充NaN值
                group['RESULT'] = group['RESULT'].interpolate(method='linear', limit_direction='both')
                # 仍有缺失值则使用前后填充
                if group['RESULT'].isna().any():
                    group['RESULT'] = group['RESULT'].fillna(method='ffill').fillna(method='bfill')

            # 确保没有缺失值
            if not group['RESULT'].isna().any():
                processed_groups.append(group)

        if not processed_groups:
            print("Warning: No valid data groups after interpolation")
            return pd.DataFrame()

        return pd.concat(processed_groups, ignore_index=True)

# ====================================================================
# 增强的预测模型 - Enhanced Prediction Model
# ====================================================================
class EnhancedPredictionModel:
    def __init__(self, config):
        self.config = config
        self.cox_stuart_config = config['model']['cox_stuart']
        self.anomaly_replacement_config = config['model']['anomaly_replacement']

    def classify_data_type(self, data_values):
        """数据类型分类函数"""
        clean_data = data_values[~np.isnan(data_values)]
        if len(clean_data) < 10:
            return 3, "数据不足，默认为波动型"

        # 计算变异系数
        cv = np.std(clean_data) / abs(np.mean(clean_data)) if np.mean(clean_data) != 0 else 0

        # 检查周期性
        from collections import Counter
        rounded_data = np.round(clean_data, 3)
        value_counts = Counter(rounded_data)
        unique_values = len(value_counts)

        if len(value_counts) >= 2:
            # 获取出现次数最多的前两个值
            top_2_counts = sum([count for _, count in value_counts.most_common(2)])
            cyclical_ratio = top_2_counts / len(clean_data)
            if cyclical_ratio > 0.70:
                return 1, f"周期性数据 (前两值占比{cyclical_ratio:.1%})"

        # 检查直线型
        if cv < 0.02 and unique_values <= 10:
            return 2, f"直线型数据 (变异系数{cv:.4f}, 独特值{unique_values}个)"

        # 默认波动型
        return 3, f"波动型数据 (变异系数{cv:.4f}, 独特值{unique_values}个)"

    def detect_cyclical_anomalies(self, data_values):
        """周期性数据异常检测 - 固定范围法"""
        from collections import Counter
        rounded_data = np.round(data_values, 3)
        value_counts = Counter(rounded_data)
        top_values = [value for value, _ in value_counts.most_common(2)]

        predicted = np.zeros_like(data_values)
        lower = np.zeros_like(data_values)
        upper = np.zeros_like(data_values)

        for i, val in enumerate(data_values):
            # 找到最接近的主要值
            if not top_values:
                center = val
            elif len(top_values) == 1:
                center = top_values[0]
            else:
                dist1 = abs(val - top_values[0])
                dist2 = abs(val - top_values[1])
                center = top_values[0] if dist1 <= dist2 else top_values[1]

            # 使用±20%区间
            range_size = abs(center) * 0.2
            lower[i] = center - range_size
            upper[i] = center + range_size

        return np.round(predicted, 3), np.round(lower, 3), np.round(upper, 3)

    def detect_trend_periods(self, data_values):
        """检测趋势期间（基于Cox-Stuart检验）"""
        n = len(data_values)
        window_size = self.cox_stuart_config['window_size']
        check_interval = self.cox_stuart_config['check_interval']
        p_threshold = self.cox_stuart_config['p_threshold']
        
        trend_periods = []
        
        for i in range(0, n - window_size + 1, check_interval):
            end_point = min(i + window_size, n)
            window_data = data_values[i:end_point]
            
            p_value = cox_stuart_test(window_data)
            
            if not np.isnan(p_value) and p_value < p_threshold:
                trend_periods.append((i, end_point))
        
        return trend_periods

    def apply_anomaly_replacement(self, data_values, predicted_values, lower_bounds, upper_bounds):
        """应用异常值替换策略（类似R代码中的逻辑）"""
        if not self.anomaly_replacement_config['enable_replacement']:
            return data_values.copy()
        
        adjusted_data = data_values.copy()
        consecutive_anomalies = 0
        stop_replacement = False
        threshold = self.anomaly_replacement_config['consecutive_threshold']
        
        for i in range(len(data_values)):
            if stop_replacement:
                break
                
            if not (np.isnan(predicted_values[i]) or np.isnan(lower_bounds[i]) or np.isnan(upper_bounds[i])):
                # 检查是否为异常值
                if data_values[i] < lower_bounds[i] or data_values[i] > upper_bounds[i]:
                    adjusted_data[i] = predicted_values[i]
                    consecutive_anomalies += 1
                    
                    if consecutive_anomalies >= threshold:
                        stop_replacement = True
                else:
                    consecutive_anomalies = 0
        
        return adjusted_data

    def enhanced_holt_winters_prediction(self, group_data):
        """增强的Holt-Winters预测（结合R代码的改进）"""
        model_config = self.config['model']
        min_data_points = model_config['min_data_points']
        lookback_window = model_config['lookback_window']
        optimize_interval = model_config['optimize_interval']
        hw_config = model_config['holt_winters']

        # 确保数据按时间排序
        sorted_data = group_data.sort_values(['TIME']).copy()

        # 获取基本信息
        mac = sorted_data['MAC'].iloc[0] if not sorted_data.empty else 'Unknown'
        itemrk = sorted_data['ITEMRK'].iloc[0] if not sorted_data.empty else 'Unknown'
        itemname = sorted_data['ITEMNAME'].iloc[0] if not sorted_data.empty and 'ITEMNAME' in sorted_data.columns else itemrk

        print(f"Processing {mac}-{itemname}: {len(sorted_data)} points")

        # 数据类型分类
        data_type, type_description = self.classify_data_type(sorted_data['RESULT'].values)
        print(f"  数据类型: {type_description}")

        # 根据数据类型选择预测方法
        if data_type == 1:  # 周期性数据
            predicted, lower, upper = self.detect_cyclical_anomalies(sorted_data['RESULT'].values)
        else:  # 波动型或直线型数据
            predicted, lower, upper = self._predict_with_enhanced_hw(sorted_data, min_data_points, 
                                                                   lookback_window, optimize_interval, hw_config)

        # 添加预测结果到数据框
        sorted_data['PREDICTED'] = predicted
        sorted_data['LOWER'] = lower
        sorted_data['UPPER'] = upper

        return sorted_data

    def _predict_with_enhanced_hw(self, sorted_data, min_data_points, lookback_window, optimize_interval, hw_config):
        """增强的Holt-Winters预测实现"""
        n = len(sorted_data)
        
        if n < min_data_points:
            print(f"  数据不足: {n} < {min_data_points}, 无法预测")
            return np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)

        # 初始化结果数组
        predicted = np.full(n, np.nan)
        lower = np.full(n, np.nan)
        upper = np.full(n, np.nan)

        # 检测趋势期间
        trend_periods = self.detect_trend_periods(sorted_data['RESULT'].values)
        print(f"  检测到 {len(trend_periods)} 个趋势期间")

        # 初始化调整后的数据
        adjusted_data = sorted_data['RESULT'].values.copy()
        
        # 滚动窗口预测
        start_index = max(min_data_points // 3 * 2, 20)  # 对应R代码中的21
        recent_errors = []
        best_alpha, best_beta = hw_config['alpha'], hw_config['beta']

        for t in range(start_index, n):
            # 获取训练数据（使用调整后的数据）
            training_days = self.config['execution']['training_history_days']
            current_time = sorted_data.iloc[t]['TIME']
            cutoff_time = current_time - pd.Timedelta(days=training_days)
            
            # 使用时间窗口和索引窗口的组合
            time_mask = (sorted_data['TIME'] >= cutoff_time) & (sorted_data['TIME'] < current_time)
            train_data = adjusted_data[time_mask]

            # 如果时间窗口数据不足，使用最近的数据点
            if len(train_data) < min_data_points:
                train_data = adjusted_data[max(0, t-min_data_points):t]

            # 检查训练数据量
            if len(train_data) < min_data_points:
                continue

            # 优化参数（每optimize_interval次迭代）
            if t == start_index or (t - start_index) % optimize_interval == 0:
                best_alpha, best_beta = self._optimize_hw_parameters(train_data, lookback_window)

            # 使用最优参数进行预测
            try:
                forecast_result = self._forecast_with_hw(train_data, best_alpha, best_beta)
                if forecast_result is not None:
                    forecast_value, confidence_interval = forecast_result
                    predicted[t] = np.round(forecast_value, 3)
                    
                    # 计算置信区间
                    if confidence_interval is not None:
                        lower[t] = np.round(confidence_interval[0], 3)
                        upper[t] = np.round(confidence_interval[1], 3)
                    else:
                        # 使用历史误差估计置信区间
                        z_value = self.config['model']['confidence_level']
                        if len(recent_errors) > 5:
                            error_std = np.std(recent_errors)
                            lower[t] = np.round(predicted[t] - z_value * error_std, 3)
                            upper[t] = np.round(predicted[t] + z_value * error_std, 3)

                    # 更新预测误差
                    if t > 0 and not np.isnan(predicted[t-1]):
                        error = abs(adjusted_data[t-1] - predicted[t-1])
                        recent_errors.append(error)
                        if len(recent_errors) > lookback_window:
                            recent_errors = recent_errors[-lookback_window:]

            except Exception as e:
                print(f"  Error predicting at point {t}: {e}")
                continue

        # 应用异常值替换策略（在获得完整预测后）
        if self.anomaly_replacement_config['enable_replacement'] and start_index < n:
            # 只对有预测值的部分应用替换
            valid_mask = ~np.isnan(predicted)
            if np.any(valid_mask):
                adjusted_section = self.apply_anomaly_replacement(
                    adjusted_data[valid_mask], 
                    predicted[valid_mask], 
                    lower[valid_mask], 
                    upper[valid_mask]
                )
                # 更新调整后的数据
                adjusted_data[valid_mask] = adjusted_section
                print(f"  应用异常值替换策略")

        return predicted, lower, upper

    def _optimize_hw_parameters(self, train_data, lookback_window):
        """优化Holt-Winters参数"""
        best_rmse = float('inf')
        best_alpha, best_beta = 0.3, 0.1

        # 简单网格搜索
        alpha_values = [0.1, 0.3, 0.5, 0.7, 0.9]
        beta_values = [0.1, 0.3, 0.5, 0.7, 0.9]

        for alpha in alpha_values:
            for beta in beta_values:
                try:
                    model = ExponentialSmoothing(
                        train_data,
                        trend='add',
                        seasonal=None,
                        damped=False
                    )
                    fit = model.fit(smoothing_level=alpha, smoothing_trend=beta, optimized=False)
                    residuals = fit.resid[~np.isnan(fit.resid)]
                    
                    if len(residuals) > lookback_window:
                        residuals = residuals[-lookback_window:]
                    
                    if len(residuals) > 0:
                        rmse = np.sqrt(np.mean(residuals**2))
                        if rmse < best_rmse:
                            best_rmse = rmse
                            best_alpha, best_beta = alpha, beta
                except:
                    continue

        return best_alpha, best_beta

    def _forecast_with_hw(self, train_data, alpha, beta, confidence_level=0.99):
        """使用Holt-Winters进行预测"""
        try:
            model = ExponentialSmoothing(
                train_data,
                trend='add',
                seasonal=None,
                damped=False
            )
            fit = model.fit(smoothing_level=alpha, smoothing_trend=beta, optimized=False)
            
            # 进行1步预测
            forecast = fit.forecast(1)
            forecast_value = forecast[0]
            
            # 计算置信区间
            try:
                # 使用残差标准误差估计置信区间
                residuals = fit.resid[~np.isnan(fit.resid)]
                if len(residuals) > 1:
                    std_error = np.std(residuals)
                    z_score = stats.norm.ppf((1 + confidence_level) / 2)
                    margin = z_score * std_error
                    confidence_interval = (forecast_value - margin, forecast_value + margin)
                else:
                    confidence_interval = None
            except:
                confidence_interval = None
            
            return forecast_value, confidence_interval
            
        except Exception as e:
            return None

    def predict_trend(self, group_data):
        """对单个MAC-ITEMRK组合进行时序预测（兼容接口）"""
        return self.enhanced_holt_winters_prediction(group_data)

# ====================================================================
# 异常检测 - Anomaly Detection
# ====================================================================
def detect_spec_anomaly(row):
    """检查单行数据的SPEC异常（基于规格上下限）"""
    if pd.isna(row['RESULT']) or pd.isna(row['UPPERLIMIT']) or pd.isna(row['LOWERLIMIT']):
        return 0

    try:
        result = clean_numeric_data(row['RESULT'])
        upper = clean_numeric_data(row['UPPERLIMIT'])
        lower = clean_numeric_data(row['LOWERLIMIT'])

        if pd.isna(result) or pd.isna(upper) or pd.isna(lower):
            return 0

        # 简单判定：RESULT超出规格范围就是异常=1，否则正常=0
        return 1 if (result > upper or result < lower) else 0
    except (ValueError, TypeError):
        return 0

def detect_fluct_anomaly(row):
    """检查单行数据的波动异常（基于预测上下限）"""
    if pd.isna(row['RESULT']) or pd.isna(row['PREDICTED_UPPER']) or pd.isna(row['PREDICTED_LOWER']):
        return 0

    try:
        result = clean_numeric_data(row['RESULT'])
        pred_upper = clean_numeric_data(row['PREDICTED_UPPER'])
        pred_lower = clean_numeric_data(row['PREDICTED_LOWER'])

        if pd.isna(result) or pd.isna(pred_upper) or pd.isna(pred_lower):
            return 0

        # 简单判定：RESULT超出预测范围就是异常=1，否则正常=0
        return 1 if (result > pred_upper or result < pred_lower) else 0
    except (ValueError, TypeError):
        return 0

class AnomalyDetector:
    def __init__(self, config):
        self.config = config

    def detect_spec_anomalies(self, df):
        """规格异常检测 - 简化版本"""
        if df.empty:
            return df

        # 批量检测SPEC异常（基于规格上下限）
        spec_eligible = df['UPPERLIMIT'].notna() & df['LOWERLIMIT'].notna() & df['RESULT'].notna()
        df['IS_SPEC_ANOMALY'] = 0  # 默认都是正常=0
        df.loc[spec_eligible, 'IS_SPEC_ANOMALY'] = df.loc[spec_eligible].apply(detect_spec_anomaly, axis=1)

        return df

    def detect_fluct_anomalies(self, df):
        """波动异常检测 - 简化版本"""
        if df.empty:
            return df

        # 批量检测波动异常（基于预测上下限）
        fluct_eligible = df['PREDICTED_UPPER'].notna() & df['PREDICTED_LOWER'].notna() & df['RESULT'].notna()
        df['IS_FLUCT_ANOMALY'] = 0  # 默认都是正常=0
        df.loc[fluct_eligible, 'IS_FLUCT_ANOMALY'] = df.loc[fluct_eligible].apply(detect_fluct_anomaly, axis=1)

        return df

# ====================================================================
# 主流程控制 - Main Workflow
# ====================================================================
class AnomalyDetectionSystem:
    def __init__(self, config):
        self.config = config
        self.db_manager = DatabaseManager(config)
        self.data_processor = DataProcessor(config)
        self.prediction_model = EnhancedPredictionModel(config)  # 使用增强版本
        self.anomaly_detector = AnomalyDetector(config)
        self.logger = setup_logging()

    def get_departments_list(self):
        """获取部门列表"""
        target_departments = self.config['execution'].get('target_departments', None)
        if target_departments:
            if isinstance(target_departments, str):
                target_departments = [target_departments]
                self.logger.warning(f"部门配置已转换为列表: {target_departments}")
            self.logger.info(f"使用部门筛选: {len(target_departments)} 个部门")
            return target_departments
        else:
            sql = """
            SELECT DISTINCT EMP_NAME
            FROM TB_BARCODE_RESULT
            WHERE EMP_NAME IS NOT NULL
            ORDER BY EMP_NAME
            """
            departments = self.db_manager.fetch_data(sql)['EMP_NAME'].tolist()
            self.logger.info(f"找到 {len(departments)} 个部门")
            return departments

    def run_prediction_stage(self, start_date, end_date):
        """运行预测阶段"""
        self.logger.info("="*80)
        self.logger.info("第一阶段：时序预测（增强版）")
        self.logger.info("="*80)

        update_progress('prediction', status='running', progress=0, message='开始时序预测阶段')

        # 获取部门列表
        departments = self.get_departments_list()
        if not departments:
            self.logger.error("未找到部门")
            update_progress('prediction', status='failed', progress=0, message='未找到部门')
            return False

        success_count = 0
        failed_departments = []

        for i, dept_name in enumerate(departments, 1):
            # 检查停止标志
            if check_stop_flag():
                self.logger.warning("检测到停止信号，中断预测阶段")
                progress = int((i / len(departments)) * 100)
                update_progress('prediction', status='cancelled', progress=progress, message='用户中断任务')
                return False

            progress = int((i / len(departments)) * 100)
            update_progress('prediction', department=dept_name, status='running', progress=progress, 
                          message=f'处理部门 {dept_name}')
            self.logger.info(f"进度 {i}/{len(departments)}: 处理部门 {dept_name}")

            try:
                # 获取源数据
                source_df = self.data_processor.fetch_source_data(
                    self.db_manager, start_date, end_date, dept_name
                )

                if source_df.empty:
                    self.logger.warning(f"部门 {dept_name} 无数据，跳过")
                    continue

                # 验证数据格式
                validate_dataframe(source_df, self.config['data_schema']['required_columns'])

                # 进行时序预测
                groups = source_df.groupby(['MAC', 'ITEMRK'])
                predicted_groups = []

                for (mac, itemrk), group_data in groups:
                    predicted_df = self.prediction_model.predict_trend(group_data)
                    predicted_groups.append(predicted_df)

                if not predicted_groups:
                    self.logger.error(f"部门 {dept_name} 无有效预测结果")
                    failed_departments.append(dept_name)
                    continue

                # 合并预测结果
                result_df = pd.concat(predicted_groups, ignore_index=True)

                # 准备更新数据
                update_data = []
                for _, row in result_df.iterrows():
                    if pd.notna(row['PREDICTED']):
                        update_data.append((
                            round(float(row['PREDICTED']), 3),
                            round(float(row['LOWER']), 3) if pd.notna(row['LOWER']) else None,
                            round(float(row['UPPER']), 3) if pd.notna(row['UPPER']) else None,
                            row['ANOMALY_RK']
                        ))

                # 更新数据库
                if update_data:
                    sql = """
                    UPDATE TB_BARCODE_RESULT
                    SET PREDICTED_VALUE = :1, PREDICTED_LOWER = :2, PREDICTED_UPPER = :3
                    WHERE ANOMALY_RK = :4
                    """
                    result = self.db_manager.batch_update(sql, update_data)
                    if result > 0:
                        self.logger.info(f"部门 {dept_name}: 更新 {result} 条预测结果")
                        success_count += 1
                    else:
                        self.logger.error(f"部门 {dept_name}: 预测结果更新失败")
                        failed_departments.append(dept_name)
                else:
                    self.logger.warning(f"部门 {dept_name}: 无预测结果需要更新")

            except Exception as e:
                self.logger.error(f"处理部门 {dept_name} 时出错: {e}")
                failed_departments.append(dept_name)
                update_progress('prediction', department=dept_name, status='failed', progress=progress, 
                              message=f'部门 {dept_name} 处理失败', error=e)

        # 完成统计
        final_message = f"预测阶段完成：成功 {success_count}/{len(departments)} 个部门"
        self.logger.info(final_message)
        if failed_departments:
            self.logger.warning(f"失败部门: {failed_departments}")

        if success_count > 0:
            update_progress('prediction', status='completed', progress=100, message=final_message)
            return True
        else:
            update_progress('prediction', status='failed', progress=100, message='预测阶段失败')
            return False

    def run_detection_stage(self, start_date, end_date):
        """运行异常检测阶段"""
        self.logger.info("="*80)
        self.logger.info("第二阶段：异常检测")
        self.logger.info("="*80)

        update_progress('detection', status='running', progress=0, message='开始异常检测阶段')

        try:
            # 检查停止标志
            if check_stop_flag():
                self.logger.warning("检测到停止信号，跳过异常检测阶段")
                update_progress('detection', status='cancelled', progress=0, message='用户中断任务')
                return False

            # 获取所有需要检测的数据
            sql = """
            SELECT ANOMALY_RK, RESULT, UPPERLIMIT, LOWERLIMIT, PREDICTED_UPPER, PREDICTED_LOWER
            FROM TB_BARCODE_RESULT
            WHERE CHECKDATE BETWEEN TO_DATE(:start_dt, 'YYYY-MM-DD') AND TO_DATE(:end_dt, 'YYYY-MM-DD')
            AND RESULT IS NOT NULL
            """

            df = self.db_manager.fetch_data(sql, {'start_dt': start_date, 'end_dt': end_date})

            if df.empty:
                message = "无数据可检测"
                self.logger.warning(message)
                update_progress('detection', status='completed', progress=100, message=message)
                return True

            self.logger.info(f"处理 {len(df)} 条记录")
            update_progress('detection', status='running', progress=30, message=f'处理 {len(df)} 条记录')

            # 执行异常检测
            df = self.anomaly_detector.detect_spec_anomalies(df)
            update_progress('detection', status='running', progress=60, message='规格异常检测完成')

            df = self.anomaly_detector.detect_fluct_anomalies(df)
            update_progress('detection', status='running', progress=80, message='波动异常检测完成')

            # 统计结果
            spec_anomalies = df['IS_SPEC_ANOMALY'].sum()
            fluct_anomalies = df['IS_FLUCT_ANOMALY'].sum()
            result_message = f"检测结果: 规格异常={spec_anomalies}, 波动异常={fluct_anomalies}"
            self.logger.info(result_message)

            # 更新数据库 - 统一更新所有记录
            update_data = []
            for _, row in df.iterrows():
                update_data.append((
                    int(row['IS_SPEC_ANOMALY']),
                    int(row['IS_FLUCT_ANOMALY']),
                    row['ANOMALY_RK']
                ))

            if update_data:
                sql = """
                UPDATE TB_BARCODE_RESULT
                SET IS_SPEC_ANOMALY = :1, IS_FLUCT_ANOMALY = :2
                WHERE ANOMALY_RK = :3
                """
                result = self.db_manager.batch_update(sql, update_data)
                if result > 0:
                    final_message = f"更新 {result} 条异常检测结果"
                    self.logger.info(final_message)
                    update_progress('detection', status='completed', progress=100, 
                                  message=f'{result_message}, {final_message}')
                    return True
                else:
                    error_message = "异常检测结果更新失败"
                    self.logger.error(error_message)
                    update_progress('detection', status='failed', progress=100, message=error_message)
                    return False
            else:
                final_message = "未发现异常，无需更新"
                self.logger.info(final_message)
                update_progress('detection', status='completed', progress=100, message=final_message)
                return True

        except Exception as e:
            error_message = f"异常检测阶段出错: {e}"
            self.logger.error(error_message)
            update_progress('detection', status='failed', progress=0, message=error_message, error=e)
            return False

    def run_full_workflow(self):
        """运行完整工作流程"""
        self.logger.info("="*100)
        self.logger.info("点检数据异常检测系统 - 完整流程（增强版）")
        self.logger.info("="*100)

        # 获取执行参数
        execution_config = self.config['execution']
        run_mode = execution_config['run_mode']
        stage_mode = execution_config.get('stage_mode', 'BOTH')

        self.logger.info(f"运行模式: {run_mode}, 阶段模式: {stage_mode}")

        if run_mode == 'DAILY':
            today = date.today()
            days_back = execution_config['daily_days_back']
            start_date = (today - timedelta(days=days_back)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            self.logger.info(f"DAILY模式: 处理最近{days_back}天数据")
        elif run_mode == 'FULL':
            start_date = execution_config['full_mode_start_date']
            end_date = execution_config['full_mode_end_date']
            self.logger.info(f"FULL模式: 处理指定时间范围")
        else:
            error_msg = f"错误: 无效的运行模式 '{run_mode}'"
            self.logger.error(error_msg)
            update_progress('system', status='failed', progress=0, message=error_msg)
            return False

        self.logger.info(f"处理时间范围: {start_date} 到 {end_date}")

        # 连接数据库
        if not self.db_manager.connect():
            error_msg = "无法连接数据库"
            self.logger.error(error_msg)
            update_progress('system', status='failed', progress=0, message=error_msg)
            return False

        try:
            success = True

            # 根据stage_mode决定运行哪些阶段
            if stage_mode in ['BOTH', 'PREDICTION_ONLY']:
                # 运行预测阶段
                if not self.run_prediction_stage(start_date, end_date):
                    self.logger.error("预测阶段失败")
                    success = False
                    if stage_mode == 'PREDICTION_ONLY':
                        return False

            if stage_mode in ['BOTH', 'DETECTION_ONLY']:
                # 运行异常检测阶段
                if not self.run_detection_stage(start_date, end_date):
                    self.logger.error("异常检测阶段失败")
                    success = False

            if success:
                final_message = "完整流程执行成功！"
                self.logger.info(final_message)
                update_progress('system', status='completed', progress=100, message=final_message)
                return True
            else:
                final_message = "部分阶段执行失败"
                self.logger.error(final_message)
                update_progress('system', status='failed', progress=100, message=final_message)
                return False

        finally:
            # 断开数据库连接
            self.db_manager.disconnect()

# ====================================================================
# 主函数 - Main Function
# ====================================================================
def main():
    """主函数"""
    logger = setup_logging()
    logger.info("启动点检数据异常检测系统（增强版）")
    logger.info("="*100)

    start_time = pytime.time()

    try:
        # 从环境变量读取配置覆盖
        config = CONFIG.copy()

        # 阶段模式
        if os.environ.get('STAGE_MODE'):
            config['execution']['stage_mode'] = os.environ.get('STAGE_MODE')
            logger.info(f"环境变量覆盖 - 阶段模式: {config['execution']['stage_mode']}")

        # 目标部门
        if os.environ.get('TARGET_DEPARTMENTS'):
            dept_list = os.environ.get('TARGET_DEPARTMENTS').split(',')
            config['execution']['target_departments'] = [d.strip() for d in dept_list]
            logger.info(f"环境变量覆盖 - 目标部门: {config['execution']['target_departments']}")

        # 时间范围
        if os.environ.get('START_DATE'):
            config['execution']['full_mode_start_date'] = os.environ.get('START_DATE')
            config['execution']['run_mode'] = 'FULL'
            logger.info(f"环境变量覆盖 - 开始日期: {config['execution']['full_mode_start_date']}")

        if os.environ.get('END_DATE'):
            config['execution']['full_mode_end_date'] = os.environ.get('END_DATE')
            config['execution']['run_mode'] = 'FULL'
            logger.info(f"环境变量覆盖 - 结束日期: {config['execution']['full_mode_end_date']}")

        # 初始化系统
        system = AnomalyDetectionSystem(config)

        # 运行完整流程
        if system.run_full_workflow():
            logger.info("系统执行完成")
        else:
            logger.error("系统执行失败")

        # 输出总执行时间
        end_time = pytime.time()
        logger.info(f"总执行时间: {(end_time - start_time)/60:.2f} 分钟")

    except Exception as e:
        logger.error(f"系统错误: {e}")
        import traceback
        traceback.print_exc()
        update_progress('system', status='failed', progress=0, message=f'系统错误: {e}', error=e)

if __name__ == "__main__":
    main()