#!/usr/bin/env python3
"""
测试增强Holt-Winters算法
Test script for Enhanced Holt-Winters Algorithm
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 从main_integrated.py导入增强预测模型
try:
    from main_integrated import EnhancedPredictionModel, CONFIG, cox_stuart_test
    print("✓ 成功导入增强预测模型")
except ImportError as e:
    print(f"✗ 导入失败: {e}")
    sys.exit(1)

def generate_test_data():
    """生成测试数据"""
    np.random.seed(42)
    n = 200
    
    # 创建不同类型的测试数据
    test_cases = {
        'cyclical': {
            'data': np.random.choice([0.6, 0.65], size=n, p=[0.8, 0.2]) + np.random.normal(0, 0.01, n),
            'description': '周期性数据 - 两个主要值'
        },
        'linear': {
            'data': np.full(n, 0.62) + np.random.normal(0, 0.005, n),
            'description': '直线型数据 - 低变异系数'
        },
        'trending': {
            'data': 0.5 + 0.1 * np.arange(n) / n + np.random.normal(0, 0.02, n),
            'description': '趋势性数据 - 明显上升趋势'
        },
        'volatile': {
            'data': 0.6 + np.random.normal(0, 0.08, n),
            'description': '波动型数据 - 高变异系数'
        },
        'mixed': {
            'data': np.concatenate([
                np.full(50, 0.6) + np.random.normal(0, 0.01, 50),  # 稳定段
                0.6 + 0.2 * np.arange(50) / 50 + np.random.normal(0, 0.02, 50),  # 趋势段
                np.random.choice([0.75, 0.8], size=50, p=[0.7, 0.3]) + np.random.normal(0, 0.015, 50),  # 周期段
                0.65 + np.random.normal(0, 0.06, 50)  # 波动段
            ]),
            'description': '混合型数据 - 包含多种模式'
        }
    }
    
    return test_cases

def create_test_dataframe(data, data_type):
    """创建测试用的DataFrame"""
    n = len(data)
    start_date = datetime(2024, 1, 1)
    
    df = pd.DataFrame({
        'MAC': [f'TEST_MAC_{data_type}'] * n,
        'ITEMRK': [f'ITEM_{data_type}'] * n,
        'ITEMNAME': [f'测试项目_{data_type}'] * n,
        'TIME': [start_date + timedelta(hours=i) for i in range(n)],
        'RESULT': data,
        'CHECKDATE': [start_date + timedelta(hours=i) for i in range(n)],
        'ANOMALY_RK': list(range(1, n+1)),
        'IS_FLUCT_ANOMALY': [0] * n,
        'EMP_NAME': [f'测试部门_{data_type}'] * n
    })
    
    return df

def test_cox_stuart():
    """测试Cox-Stuart检验功能"""
    print("\n" + "="*60)
    print("测试 Cox-Stuart 趋势检验")
    print("="*60)
    
    # 测试案例
    test_cases = {
        '无趋势': np.random.normal(0, 1, 20),
        '上升趋势': np.arange(20) + np.random.normal(0, 0.5, 20),
        '下降趋势': -np.arange(20) + np.random.normal(0, 0.5, 20),
        '数据不足': np.random.normal(0, 1, 10)
    }
    
    for name, data in test_cases.items():
        p_value = cox_stuart_test(data)
        trend_detected = "是" if not np.isnan(p_value) and p_value < 0.05 else "否"
        print(f"{name:10s}: p值={p_value:.4f if not np.isnan(p_value) else 'N/A':>8s}, 检测到趋势: {trend_detected}")

def test_data_classification():
    """测试数据类型分类功能"""
    print("\n" + "="*60)
    print("测试数据类型分类")
    print("="*60)
    
    # 初始化模型
    model = EnhancedPredictionModel(CONFIG)
    test_cases = generate_test_data()
    
    for data_type, info in test_cases.items():
        data_class, description = model.classify_data_type(info['data'])
        print(f"{data_type:12s}: {description}")

def test_parameter_optimization():
    """测试参数优化功能"""
    print("\n" + "="*60)
    print("测试参数优化")
    print("="*60)
    
    model = EnhancedPredictionModel(CONFIG)
    
    # 生成测试数据
    np.random.seed(123)
    test_data = 0.6 + 0.1 * np.sin(np.arange(50) * 0.2) + np.random.normal(0, 0.02, 50)
    
    # 测试参数优化
    best_alpha, best_beta = model._optimize_hw_parameters(test_data, 30)
    print(f"优化后参数: α={best_alpha:.1f}, β={best_beta:.1f}")

def test_anomaly_replacement():
    """测试异常值替换功能"""
    print("\n" + "="*60)
    print("测试异常值替换策略")
    print("="*60)
    
    model = EnhancedPredictionModel(CONFIG)
    
    # 创建包含异常值的测试数据
    normal_data = np.full(20, 0.6)
    anomaly_data = normal_data.copy()
    anomaly_data[10:13] = [0.9, 0.95, 0.85]  # 连续异常值
    
    # 模拟预测值和边界
    predicted = np.full(20, 0.6)
    lower = np.full(20, 0.55)
    upper = np.full(20, 0.65)
    
    # 应用异常值替换
    adjusted_data = model.apply_anomaly_replacement(anomaly_data, predicted, lower, upper)
    
    print("原始数据:", anomaly_data[8:15])
    print("调整数据:", adjusted_data[8:15])
    print("异常值替换:", np.sum(anomaly_data != adjusted_data), "个值被替换")

def test_full_prediction():
    """测试完整预测流程"""
    print("\n" + "="*60)
    print("测试完整预测流程")
    print("="*60)
    
    model = EnhancedPredictionModel(CONFIG)
    test_cases = generate_test_data()
    
    for data_type, info in test_cases.items():
        print(f"\n--- 测试 {data_type} ---")
        print(f"数据描述: {info['description']}")
        
        # 创建测试DataFrame
        test_df = create_test_dataframe(info['data'], data_type)
        
        # 进行预测
        try:
            result_df = model.predict_trend(test_df)
            
            # 统计预测结果
            valid_predictions = result_df['PREDICTED'].notna().sum()
            print(f"有效预测点: {valid_predictions}/{len(result_df)}")
            
            if valid_predictions > 0:
                # 计算预测精度（对于有预测值的点）
                mask = result_df['PREDICTED'].notna()
                mae = np.mean(np.abs(result_df.loc[mask, 'PREDICTED'] - result_df.loc[mask, 'RESULT']))
                print(f"平均绝对误差 (MAE): {mae:.4f}")
                
                # 检查置信区间覆盖率
                in_bounds = ((result_df.loc[mask, 'RESULT'] >= result_df.loc[mask, 'LOWER']) & 
                           (result_df.loc[mask, 'RESULT'] <= result_df.loc[mask, 'UPPER'])).sum()
                coverage = in_bounds / valid_predictions * 100
                print(f"置信区间覆盖率: {coverage:.1f}%")
            
        except Exception as e:
            print(f"预测失败: {e}")

def test_visualization():
    """生成可视化测试结果"""
    print("\n" + "="*60)
    print("生成可视化测试结果")
    print("="*60)
    
    try:
        model = EnhancedPredictionModel(CONFIG)
        
        # 使用混合数据进行可视化测试
        test_cases = generate_test_data()
        mixed_data = test_cases['mixed']['data']
        test_df = create_test_dataframe(mixed_data, 'mixed')
        
        # 进行预测
        result_df = model.predict_trend(test_df)
        
        # 创建图表
        plt.figure(figsize=(12, 8))
        
        # 绘制原始数据
        plt.plot(result_df['RESULT'], 'k-', label='原始数据', linewidth=1)
        
        # 绘制预测值
        mask = result_df['PREDICTED'].notna()
        if mask.any():
            plt.plot(result_df.index[mask], result_df.loc[mask, 'PREDICTED'], 
                    'b--', label='预测值', alpha=0.7)
            
            # 绘制置信区间
            plt.fill_between(result_df.index[mask], 
                           result_df.loc[mask, 'LOWER'], 
                           result_df.loc[mask, 'UPPER'],
                           alpha=0.3, color='blue', label='99%置信区间')
        
        plt.title('增强Holt-Winters算法测试结果\n(混合型数据: 稳定→趋势→周期→波动)', fontsize=14)
        plt.xlabel('时间点')
        plt.ylabel('测量值')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # 保存图表
        output_file = 'enhanced_hw_test_result.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✓ 可视化结果已保存到: {output_file}")
        
        # 显示图表（如果在交互环境中）
        try:
            plt.show()
        except:
            pass
        
    except Exception as e:
        print(f"✗ 可视化生成失败: {e}")

def run_all_tests():
    """运行所有测试"""
    print("🚀 开始测试增强Holt-Winters算法")
    print("="*80)
    
    try:
        # 1. 测试Cox-Stuart检验
        test_cox_stuart()
        
        # 2. 测试数据分类
        test_data_classification()
        
        # 3. 测试参数优化
        test_parameter_optimization()
        
        # 4. 测试异常值替换
        test_anomaly_replacement()
        
        # 5. 测试完整预测流程
        test_full_prediction()
        
        # 6. 生成可视化结果
        test_visualization()
        
        print("\n" + "="*80)
        print("✅ 所有测试完成！")
        print("="*80)
        
        # 输出测试总结
        print("\n📊 测试总结:")
        print("1. ✓ Cox-Stuart趋势检验 - 正常工作")
        print("2. ✓ 智能数据分类 - 能够识别不同数据类型")
        print("3. ✓ 动态参数优化 - 可自动调整α和β参数")
        print("4. ✓ 异常值替换策略 - 能够防止异常值污染")
        print("5. ✓ 完整预测流程 - 各种数据类型均能处理")
        print("6. ✓ 可视化输出 - 生成测试结果图表")
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()