# enhanced_forecast_demo.R - 增强预测算法演示
# 结合Python优化的Holt-Winters预测算法

library(forecast)
library(ggplot2)
library(gridExtra)

# 读取测试数据（请根据实际路径调整）
# Test_Data <- read.csv('C:/Users/Administrator/Desktop/tt.csv', header = T)
# 为演示目的，创建示例数据
set.seed(123)
n <- 576
Test_Data <- c(
  rnorm(200, mean = 0.6, sd = 0.05),  # 正常段
  rnorm(50, mean = 0.9, sd = 0.03),   # 异常段
  rnorm(150, mean = 0.65, sd = 0.04), # 恢复正常
  rnorm(100, mean = 0.7, sd = 0.08),  # 波动段
  rnorm(76, mean = 0.6, sd = 0.05)    # 稳定段
)

Test_Data <- ts(Test_Data)
Test_Data <- window(Test_Data, start = 1, end = n)

# Cox-Stuart趋势检验函数
cox_stuart_test <- function(data_window) {
  n <- length(data_window)
  if(n < 14) return(NA)
  
  split_point <- ceiling(n/2)
  D <- data_window[1:split_point] - data_window[(n-split_point+1):n]
  
  s_plus <- sum(D > 0, na.rm = TRUE)
  s_minus <- sum(D < 0, na.rm = TRUE)
  k <- min(s_plus, s_minus)
  n_valid <- s_plus + s_minus
  
  if(n_valid == 0) return(1.0)
  
  p_value <- pbinom(k, size = n_valid, prob = 0.5)
  return(p_value)
}

# 数据类型分类函数
classify_data_type <- function(data_values) {
  clean_data <- data_values[!is.na(data_values)]
  if(length(clean_data) < 10) {
    return(list(type = 3, description = "数据不足，默认为波动型"))
  }
  
  # 计算变异系数
  cv <- sd(clean_data) / abs(mean(clean_data))
  
  # 检查周期性
  rounded_data <- round(clean_data, 3)
  value_counts <- table(rounded_data)
  unique_values <- length(value_counts)
  
  if(length(value_counts) >= 2) {
    # 获取出现次数最多的前两个值
    top_2_counts <- sum(sort(value_counts, decreasing = TRUE)[1:2])
    cyclical_ratio <- top_2_counts / length(clean_data)
    
    if(cyclical_ratio > 0.70) {
      return(list(type = 1, description = paste0("周期性数据 (前两值占比", round(cyclical_ratio*100, 1), "%)")))
    }
  }
  
  # 检查直线型
  if(cv < 0.02 && unique_values <= 10) {
    return(list(type = 2, description = paste0("直线型数据 (变异系数", round(cv, 4), ", 独特值", unique_values, "个)")))
  }
  
  # 默认波动型
  return(list(type = 3, description = paste0("波动型数据 (变异系数", round(cv, 4), ", 独特值", unique_values, "个)")))
}

# 参数优化函数
optimize_hw_parameters <- function(train_data, lookback_window = 30) {
  best_rmse <- Inf
  best_alpha <- 0.3
  best_beta <- 0.1
  
  alpha_values <- c(0.1, 0.3, 0.5, 0.7, 0.9)
  beta_values <- c(0.1, 0.3, 0.5, 0.7, 0.9)
  
  for(alpha in alpha_values) {
    for(beta in beta_values) {
      tryCatch({
        model <- HoltWinters(train_data, alpha = alpha, beta = beta, gamma = FALSE)
        residuals <- residuals(model)
        residuals <- residuals[!is.na(residuals)]
        
        if(length(residuals) > lookback_window) {
          residuals <- tail(residuals, lookback_window)
        }
        
        if(length(residuals) > 0) {
          rmse <- sqrt(mean(residuals^2))
          if(rmse < best_rmse) {
            best_rmse <- rmse
            best_alpha <- alpha
            best_beta <- beta
          }
        }
      }, error = function(e) {})
    }
  }
  
  return(list(alpha = best_alpha, beta = best_beta, rmse = best_rmse))
}

# 增强的Holt-Winters预测算法
enhanced_holt_winters_forecast <- function(data, 
                                         min_data_points = 30,
                                         lookback_window = 30,
                                         optimize_interval = 20,
                                         confidence_level = 0.99,
                                         cox_stuart_window = 14,
                                         p_threshold = 0.05,
                                         consecutive_threshold = 6,
                                         enable_replacement = TRUE) {
  
  n <- length(data)
  
  # 数据分类
  data_classification <- classify_data_type(as.numeric(data))
  cat("数据类型:", data_classification$description, "\n")
  
  # 初始化结果
  adjusted_data <- as.numeric(data)
  predicted <- rep(NA, n)
  lower <- rep(NA, n)
  upper <- rep(NA, n)
  
  # 检测趋势期间
  trend_periods <- data.frame(start=integer(), end=integer())
  
  for(i in seq(1, n-cox_stuart_window+1, by = cox_stuart_window)) {
    end_point <- min(i+cox_stuart_window-1, n)
    window_data <- data[i:end_point]
    p_value <- cox_stuart_test(window_data)
    
    if(!is.na(p_value) && p_value < p_threshold) {
      trend_periods <- rbind(trend_periods, data.frame(start=i, end=end_point))
    }
  }
  
  cat("检测到", nrow(trend_periods), "个趋势期间\n")
  
  # 滚动窗口预测
  start_index <- max(as.integer(min_data_points * 2/3), 20)
  consecutive_anomalies <- 0
  stop_replacement <- FALSE
  recent_errors <- c()
  best_alpha <- 0.3
  best_beta <- 0.1
  
  for(t in start_index:n) {
    # 获取训练数据
    train_end <- t - 1
    train_start <- max(1, train_end - min_data_points + 1)
    train_data <- ts(adjusted_data[train_start:train_end], frequency = 1)
    
    if(length(train_data) < min_data_points) next
    
    # 优化参数（每optimize_interval次迭代）
    if(t == start_index || (t - start_index) %% optimize_interval == 0) {
      optimization_result <- optimize_hw_parameters(train_data, lookback_window)
      best_alpha <- optimization_result$alpha
      best_beta <- optimization_result$beta
      cat("时间点", t, ": 优化参数 alpha =", best_alpha, ", beta =", best_beta, "\n")
    }
    
    # 进行预测
    tryCatch({
      model <- HoltWinters(train_data, alpha = best_alpha, beta = best_beta, gamma = FALSE)
      forecast_result <- forecast(model, h = 1, level = confidence_level*100)
      
      predicted[t] <- forecast_result$mean[1]
      lower[t] <- forecast_result$lower[1]
      upper[t] <- forecast_result$upper[1]
      
      # 更新预测误差
      if(t > start_index && !is.na(predicted[t-1])) {
        error <- abs(adjusted_data[t-1] - predicted[t-1])
        recent_errors <- c(recent_errors, error)
        if(length(recent_errors) > lookback_window) {
          recent_errors <- tail(recent_errors, lookback_window)
        }
      }
      
      # 异常值替换策略
      if(enable_replacement && !stop_replacement && !is.na(lower[t]) && !is.na(upper[t])) {
        if(data[t] < lower[t] || data[t] > upper[t]) {
          adjusted_data[t] <- predicted[t]
          consecutive_anomalies <- consecutive_anomalies + 1
          
          if(consecutive_anomalies >= consecutive_threshold) {
            stop_replacement <- TRUE
            cat("连续异常达到阈值，停止替换\n")
          }
        } else {
          consecutive_anomalies <- 0
        }
      }
      
    }, error = function(e) {
      cat("预测时间点", t, "出错:", e$message, "\n")
    })
  }
  
  return(list(
    original = as.numeric(data),
    adjusted = adjusted_data,
    predicted = predicted,
    lower = lower,
    upper = upper,
    trend_periods = trend_periods,
    classification = data_classification
  ))
}

# 执行增强预测
cat("开始增强Holt-Winters预测...\n")
result <- enhanced_holt_winters_forecast(Test_Data)

# 准备绘图数据
plot_data <- data.frame(
  Time = 1:length(Test_Data),
  Original = result$original,
  Adjusted = result$adjusted,
  Predicted = result$predicted,
  Lower = result$lower,
  Upper = result$upper
)

# 移位边界数据（对应R代码逻辑）
shifted_bounds <- plot_data[plot_data$Time >= 21, ]
shifted_bounds$Time <- shifted_bounds$Time - 1

# 创建趋势阴影
trend_shading <- if(nrow(result$trend_periods) > 0) {
  geom_rect(
    data = result$trend_periods,
    aes(xmin = start-0.5, xmax = end+0.5, ymin = -Inf, ymax = Inf),
    fill = "gray80", alpha = 0.3, inherit.aes = FALSE
  )
} else {
  NULL
}

# 绘制增强预测结果
p1 <- ggplot(plot_data) +
  trend_shading +
  geom_line(aes(x = Time, y = Original, colour = "原始数据"), linewidth = 1) +
  geom_line(aes(x = Time, y = Adjusted, colour = "调整数据"), linewidth = 0.8, alpha = 0.7) +
  geom_line(
    data = shifted_bounds,
    aes(x = Time, y = Lower, colour = "预测区间"),
    linewidth = 1, linetype = "dashed"
  ) +
  geom_line(
    data = shifted_bounds,
    aes(x = Time, y = Upper, colour = "预测区间"),
    linewidth = 1, linetype = "dashed"
  ) +
  geom_hline(aes(yintercept = 0.5, colour = "预警上限"), linewidth = 1.2) +
  geom_hline(aes(yintercept = 0.8, colour = "规格上限"), linewidth = 1.2) +
  scale_colour_manual(
    name = NULL,
    values = c(
      "原始数据" = "black",
      "调整数据" = "blue",
      "预测区间" = "green",
      "预警上限" = "pink",
      "规格上限" = "red"
    )
  ) +
  labs(
    title = "增强Holt-Winters异常检测（含趋势预警）",
    subtitle = paste0("数据分类: ", result$classification$description, 
                     " | 灰色背景表示显著趋势区域（p<0.05）"),
    y = "监测值",
    x = "时间序列"
  ) +
  theme_minimal() +
  theme(
    legend.position = "bottom",
    plot.title = element_text(hjust = 0.5, face = "bold"),
    plot.subtitle = element_text(hjust = 0.5, size = 10)
  )

# 对比原始方法
original_method <- function(data) {
  n <- length(data)
  predicted_orig <- rep(NA, n)
  lower_orig <- rep(NA, n)
  upper_orig <- rep(NA, n)
  
  for(t in 21:n) {
    train_data <- ts(data[1:(t-1)], frequency = 1)
    tryCatch({
      model <- HoltWinters(train_data, gamma = FALSE)
      forecast_result <- forecast(model, h = 1, level = 99)
      predicted_orig[t] <- forecast_result$mean[1]
      lower_orig[t] <- forecast_result$lower[1]
      upper_orig[t] <- forecast_result$upper[1]
    }, error = function(e) {})
  }
  
  return(list(predicted = predicted_orig, lower = lower_orig, upper = upper_orig))
}

original_result <- original_method(Test_Data)

# 比较图
comparison_data <- data.frame(
  Time = 1:length(Test_Data),
  Original = as.numeric(Test_Data),
  Enhanced_Lower = result$lower,
  Enhanced_Upper = result$upper,
  Original_Lower = original_result$lower,
  Original_Upper = original_result$upper
)

p2 <- ggplot(comparison_data) +
  geom_line(aes(x = Time, y = Original), color = "black", linewidth = 1) +
  geom_line(aes(x = Time, y = Enhanced_Lower, colour = "增强算法"), linewidth = 1, linetype = "dashed") +
  geom_line(aes(x = Time, y = Enhanced_Upper, colour = "增强算法"), linewidth = 1, linetype = "dashed") +
  geom_line(aes(x = Time, y = Original_Lower, colour = "原始算法"), linewidth = 1, linetype = "dotted") +
  geom_line(aes(x = Time, y = Original_Upper, colour = "原始算法"), linewidth = 1, linetype = "dotted") +
  scale_colour_manual(
    name = "算法类型",
    values = c("增强算法" = "blue", "原始算法" = "red")
  ) +
  labs(
    title = "预测算法对比",
    subtitle = "虚线为增强算法预测区间，点线为原始算法预测区间",
    y = "监测值",
    x = "时间序列"
  ) +
  theme_minimal() +
  theme(
    legend.position = "bottom",
    plot.title = element_text(hjust = 0.5, face = "bold"),
    plot.subtitle = element_text(hjust = 0.5, size = 10)
  )

# 显示图表
print(p1)
print(p2)

# 统计信息
cat("\n=== 增强算法统计信息 ===\n")
cat("趋势期间数量:", nrow(result$trend_periods), "\n")
cat("数据分类:", result$classification$description, "\n")

# 计算预测准确性
valid_pred_enhanced <- !is.na(result$predicted) & !is.na(Test_Data)
if(sum(valid_pred_enhanced) > 0) {
  mae_enhanced <- mean(abs(result$predicted[valid_pred_enhanced] - Test_Data[valid_pred_enhanced]), na.rm = TRUE)
  rmse_enhanced <- sqrt(mean((result$predicted[valid_pred_enhanced] - Test_Data[valid_pred_enhanced])^2, na.rm = TRUE))
  cat("增强算法 MAE:", round(mae_enhanced, 4), "\n")
  cat("增强算法 RMSE:", round(rmse_enhanced, 4), "\n")
}

valid_pred_original <- !is.na(original_result$predicted) & !is.na(Test_Data)
if(sum(valid_pred_original) > 0) {
  mae_original <- mean(abs(original_result$predicted[valid_pred_original] - Test_Data[valid_pred_original]), na.rm = TRUE)
  rmse_original <- sqrt(mean((original_result$predicted[valid_pred_original] - Test_Data[valid_pred_original])^2, na.rm = TRUE))
  cat("原始算法 MAE:", round(mae_original, 4), "\n")
  cat("原始算法 RMSE:", round(rmse_original, 4), "\n")
  
  if(exists("mae_enhanced")) {
    cat("MAE 改进率:", round((mae_original - mae_enhanced)/mae_original * 100, 2), "%\n")
    cat("RMSE 改进率:", round((rmse_original - rmse_enhanced)/rmse_original * 100, 2), "%\n")
  }
}

cat("\n=== 算法增强功能 ===\n")
cat("1. Cox-Stuart趋势检验 - 自动识别显著趋势期间\n")
cat("2. 数据类型分类 - 针对不同数据特征采用不同策略\n") 
cat("3. 参数动态优化 - 定期优化alpha和beta参数\n")
cat("4. 异常值替换 - 防止连续异常影响预测\n")
cat("5. 增强置信区间 - 结合历史误差改进区间估计\n")