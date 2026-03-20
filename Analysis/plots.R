###    Invariant Causal Knowledge (Study 1)     ###
###        Randall Hale, Patricia Cheng         ###


library(ggplot2)

# Example data
df <- data.frame(
  num_dms = c(1, 2, 3),
  causal_judgment_time = c(.976, 1.069, 1.064),
  lower = c(.429, .559, .641),
  upper = c(1.52, 1.54, 1.49)
)

ggplot(df, aes(x = x, y = y)) +
  geom_line(color = "blue", size = 1, linetype="dashed") +              # function line
  geom_point(color = "blue", size = 2) +             # data points
  geom_errorbar(aes(ymin = lower, ymax = upper),     # CI bars
                width = 0.2, color = "black") +
  labs(x = "X", y = "Y", title = "Function with 95% CI (Error Bars)") +
  theme_minimal()



emm_dm <- data.frame(
  num_dm = factor(1:3),   # Make it a factor for discrete x-axis
  emmean = c(2.80, 2.89, 2.89),
  SE = c(0.130, 0.116, 0.119),
  lower.CL = c(2.54, 2.65, 2.65),
  upper.CL = c(3.06, 3.12, 3.13)
)

# Create bar plot with 95% CI error bars
ggplot(emm_dm, aes(x = num_dm, y = emmean)) +
  geom_bar(stat = "identity", fill = "skyblue", color = "black", width = 0.6) +
  geom_errorbar(aes(ymin = lower.CL, ymax = upper.CL), width = 0.2) +
  labs(x = "num_dm", y = "Estimated Mean", title = "Estimated Marginal Means with 95% CI") +
  scale_y_continuous(limits = c(0, 4)) +   # Fixed y-axis from 0 to 4
  theme_minimal(base_size = 14)



emm_dm <- data.frame(
  num_dm = factor(1:3),
  emmean = c(95.3, 92.2, 91.3),
  SE = c(2.21, 1.57, 1.72),
  lower.CL = c(91.0, 89.1, 87.9),
  upper.CL = c(99.7, 95.4, 94.8)
)

# Plot line with 95% CI error bars
ggplot(emm_dm, aes(x = num_dm, y = emmean, group = 1)) +
  geom_line(color = "steelblue", linewidth = 1) +
  geom_point(size = 3, color = "steelblue") +
  geom_errorbar(aes(ymin = lower.CL, ymax = upper.CL), width = 0.1, color = "gray30") +
  labs(
    x = "num_dm",
    y = "confidence",
    title = "Estimated Marginal Means with 95% CI"
  ) +
  scale_y_continuous(limits = c(0, 100)) +  # optional fixed y-axis range
  theme_minimal(base_size = 14)
