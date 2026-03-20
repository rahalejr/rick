library(lme4)
library(emmeans)
library(tidyverse)

#### NOTE: check stim 18 is updated to be 3-dm

# Fit your model with baseline RT as covariate
fit <- lmer(
  TCJ ~ condition + PRE + baseline_RT + (1 + condition | sim_index) + (1 | participant),
  data = data,
  REML = TRUE
)

# EMMs at baseline RT = 0
emm_nc <- emmeans(fit, ~ condition, at = list(baseline_RT = 0))

# Define the 8:11 contrast: 11*mu2 - 8*mu5
ratio_contrast <- contrast(emm_nc, method = list(
  "CSM_ratio" = c("two_candidate" = 11, "five_candidate" = -8)
))

# Summarize the test
summary(ratio_contrast, infer = TRUE)




causal_rt <- readRDS("data/cleaned/causal_rt.rds")
outcome_rt <- readRDS("data/cleaned/outcome_rt.rds")

data <- causal_rt


data <- data %>% 
  filter(participant != 0) %>%
  mutate(across(c(collision, num_dm, preemption, participant, participant_id), as.factor))

data_clean <- data |>
  group_by(num_dm) |>
  mutate(
    mean_rt = mean(RT, na.rm = TRUE),
    sd_rt   = sd(RT, na.rm = TRUE),
    keep    = (RT > mean_rt - 2 * sd_rt) & (RT < mean_rt + 2 * sd_rt)
  ) |>
  filter(keep) |>
  ungroup()


model <- lmer(RT ~ num_dm + baseline_RT + preemption + duration + last_collision +  (1 + num_dm | participant_id) + (1 | collision), data = data_clean,
              control = lmerControl(optimizer = "bobyqa"))

emm <- emmeans(model, ~ num_dm)


con <- contrast(
  emm,
  method = list(
    `DM2 - DM1` = c(-1,  1,  0),
    `DM3 - DM2` = c( 0, -1,  1),
    `DM3 - DM1` = c(-1,  0,  1)
  )
)

# Two-sided tests + 95% CIs (default)
summary(con, infer = c(TRUE, TRUE))

cond_effects <- contrast(emm)

final_contrast <- contrast(cond_effects, 
                           method = list("Hypothesis_Test" = c(-21/9, 0, 1)),
                           by = NULL) 

summary(final_contrast, side = "<")




emm_df <- as.data.frame(emm)


ggplot(emm_df, aes(
  x = factor(num_dm, levels = sort(unique(num_dm))),
  y = emmean,
  group = 1
)) +
  geom_line(linewidth = 1, color = "grey30") +
  geom_errorbar(
    aes(ymin = lower.CL, ymax = upper.CL),
    width = 0.1,
    color = "grey0",
    linetype = "solid",
    show.legend = FALSE
  ) +
  scale_y_continuous(
    limits = c(0, 4),
    expand = c(0, 0)
  ) +
  scale_x_discrete(name = "Difference-makers") +
  ylab("Covariate-adjusted RT (s)") +
  theme_minimal(base_family = "Lora", base_size = 14) +
  theme(
    panel.grid.minor = element_blank(),
    legend.text  = element_text(size = 10),
    axis.title.x = element_text(size = 12),
    axis.title.y = element_text(size = 12),
    axis.text.x  = element_text(size = 10),
    axis.text.y  = element_text(size = 10)
  )

ggplot(emm_df, aes(
  x = factor(num_dm, levels = sort(unique(num_dm))),
  y = emmean,
  group = 1
)) +
  geom_line(linewidth = 1, color = "grey30") +
  geom_errorbar(aes(ymin = lower.CL, ymax = upper.CL),
                width = 0.1, color = "grey0") +
  scale_y_continuous(limits = c(0, 4), expand = c(0, 0)) +
  scale_x_discrete(name = "Difference-makers") +
  ylab("Covariate-adjusted RT (s)") +
  theme_minimal(base_size = 14) +   # <- no base_family
  theme(
    panel.grid.minor = element_blank(),
    legend.text  = element_text(size = 10),
    axis.title.x = element_text(size = 12),
    axis.title.y = element_text(size = 12),
    axis.text.x  = element_text(size = 10),
    axis.text.y  = element_text(size = 10)
  )


############## ATTRIBUTION


attr <- readRDS("data/cleaned/causal_attr.rds")
data <- attr %>% 
  filter(participant != 0, rational == T) %>%
  mutate(across(c(collision, num_dm, condition, order, preemption, participant, participant_id), as.factor))

csm <- readRDS("data/cleaned/csm.rds")

attr_csm <- attr %>%
  left_join(
    csm,
    by = c("collision" = "stimulus",
           "order"     = "order")
  )

attr_csm_gated <- attr_csm %>%
  mutate(
    WHETHER_g = WHETHER * DM,
    HOW_g = HOW * DM,
    SUFFICIENT_g = SUFFICIENT * DM,
    ROBUST_g = ROBUST * DM
  )

attr_csm_gated[attr_csm_gated$collision == 18,]$num_dm = 3

attr_csm_gated = attr_csm_gated %>% mutate(across(c(collision, num_dm, condition, order, preemption, participant, participant_id), as.factor))

saveRDS(attr_csm_gated, "data/cleaned/attr_comparison.rds")


################ FITTING CSM WEIGHTS #####################

m_full <- lmer(
  attribution ~ 1 + WHETHER_g + HOW_g + SUFFICIENT_g + ROBUST_g +
    (1 | participant) + (1 | collision),
  data = attr_csm_gated,
  REML = FALSE,
  control = lmerControl(optimizer = "bobyqa")
)


attr_csm_gated$pred_csm <- predict(m_full, re.form = NA)

#########################################################

df_csm <- attr_csm_gated %>%
  group_by(num_dm, order) %>%
  summarise(
    emmean = mean(pred_csm),
    lower.CL = emmean - 1.96 * sd(pred_csm) / sqrt(n()),
    upper.CL = emmean + 1.96 * sd(pred_csm) / sqrt(n()),
    .groups = "drop"
  ) %>%
  mutate(
    ymin = lower.CL,
    ymax = upper.CL,
    order = factor(order)
  )

install.packages("showtext")
library(showtext)

font_add_google("Lora", "Lora")
showtext_auto()

ggplot(df_csm, aes(
  x = factor(num_dm),
  y = emmean,
  fill = order
)) +
  geom_col(
    position = position_dodge(width = 0.8),
    width = 0.7
  ) +
  geom_errorbar(
    aes(ymin = ymin, ymax = ymax),
    width = 0.2,
    position = position_dodge(width = 0.8)
  ) +
  scale_x_discrete(name = "Difference-makers") +
  scale_y_continuous(
    limits = c(-4, 100),
    expand = c(0, 0)
  ) +
  ylab("Attribution") +
  theme_minimal(base_size = 14) +
  theme(
    panel.grid.minor = element_blank(),
    axis.title.x = element_text(
      family = "Lora",
      size = 12
    ),
    axis.title.y = element_text(
      family = "Lora",
      size = 12
    ),
    axis.text.x = element_text(
      family = "Lora",
      size = 10
    ),
    legend.text  = element_text(
      family = "Lora",
      size = 10
    ),
    legend.title  = element_text(
      family = "Lora",
      size = 10
    ),
    axis.text.y = element_text(
      family = "Lora",
      size = 10
    )) +
  scale_fill_manual(
    name = 'Order',
    values = c(
      "3" = "grey25",
      "2" = "grey45",
      "1" = "grey65"
    ))
  



##########################################################
######### MODELING AND PLOTTING PARTICIPANT DATA #########
##########################################################

model <- lmer(
  divergence ~ preemption + num_dm * order + duration + last_collision + baseline_RT +
    (1 + order | participant_id) +
    (1 | collision),
  data = attr_csm_gated,
  control = lmerControl(optimizer = "bobyqa")
)

emm <- emmeans(model, ~ order | num_dm)
emm_df <- as.data.frame(emm)

df_human <- emm_df %>%
  mutate(
    num_dm = factor(num_dm),
    order  = factor(order),
    ymin   = lower.CL,
    ymax   = upper.CL
  )

ggplot(df_human, aes(
  x = factor(num_dm),
  y = emmean,
  fill = order
)) +
  geom_col(
    position = position_dodge(width = 0.8),
    width = 0.7
  ) +
  geom_errorbar(
    aes(ymin = ymin, ymax = ymax),
    width = 0.2,
    position = position_dodge(width = 0.8)
  ) +
  scale_x_discrete(name = "Difference-makers") +
  scale_y_continuous(
    limits = c(-4, 100),
    expand = c(0, 0)
  ) +
  ylab("Attribution") +
  theme_minimal(base_size = 14) +
  theme(
    panel.grid.minor = element_blank(),
    axis.title.x = element_text(
      family = "Lora",
      size = 12
    ),
    axis.title.y = element_text(
      family = "Lora",
      size = 12
    ),
    axis.text.x = element_text(
      family = "Lora",
      size = 10
    ),
    legend.text  = element_text(
      family = "Lora",
      size = 10
    ),
    legend.title  = element_text(
      family = "Lora",
      size = 10
    ),
    axis.text.y = element_text(
      family = "Lora",
      size = 10
    )) +
  scale_fill_manual(
    name = 'Order',
    values = c(
      "3" = "grey25",
      "2" = "grey45",
      "1" = "grey65"
    ))

###########################################################
############# MODELING AND PLOTTING CSM ERROR #############
###########################################################

attr_csm_gated$divergence <- abs(attr_csm_gated$attribution - attr_csm_gated$pred_csm)
data <- attr_csm_gated

saveRDS(data, "data/cleaned/divergence.rds")

df_div_plot <- data %>%
  group_by(num_dm, order) %>%
  summarise(
    mean_div = mean(divergence),
    se_div   = sd(divergence) / sqrt(n()),
    lower    = mean_div - 1.96 * se_div,
    upper    = mean_div + 1.96 * se_div,
    .groups  = "drop"
  ) %>%
  mutate(
    num_dm = factor(num_dm),
    order  = factor(order)
  )

ggplot(df_div_plot, aes(
  x = num_dm,
  y = mean_div,
  group = order,
  color = order
)) +
  scale_y_continuous(
    limits = c(0, 52),
    expand = c(0, 0)
  ) +
  geom_hline(yintercept = 0, linetype = "solid", color = "grey50") +
  geom_vline(xintercept = .5, linetype = "solid", color = "grey50") +
  geom_line(size = 1) +
  geom_point(size = 2) +
  geom_errorbar(
    aes(ymin = lower, ymax = upper),
    width = 0.1
  ) +
  scale_color_manual(
    name = "Order",
    values = c(
      "1" = "#332288",  # muted indigo
      "2" = "#117733",  # muted green
      "3" = "#882255"   # muted wine
    )
  ) +
  scale_x_discrete(name = "Difference-makers") +
  ylab("Human − CSM divergence") +
  coord_cartesian(xlim = c(1, 3)) +
  theme_minimal(base_family = "Lora", base_size = 14) +
  theme(
    panel.grid.minor = element_blank(),
    legend.title = element_text(size = 12),
    legend.text  = element_text(size = 10),
    axis.title.x = element_text(size = 12),
    axis.title.y = element_text(size = 12),
    axis.text.x  = element_text(size = 10),
    axis.text.y  = element_text(size = 10)
  )

ggplot(df_div_plot, aes(
  x = num_dm,
  y = mean_div,
  group = order,
  linetype = order
)) +
  scale_y_continuous(limits = c(0, 52), expand = c(0, 0)) +
  geom_hline(yintercept = 0, color = "grey50") +
  geom_vline(xintercept = .5, color = "grey50") +
  geom_line(size = 1, color = "grey30") +
  geom_point(size = 2, color = "grey30") +
  geom_errorbar(
    aes(ymin = lower, ymax = upper),
    width = 0.1,
    color = "grey0",
    linetype = "solid",
    show.legend = FALSE
  ) +
  scale_linetype_manual(
    name = "Order",
    values = c(
      "1" = "solid",
      "2" = "dashed",
      "3" = "dotted"
    )
  ) +
  scale_x_discrete(name = "Difference-makers") +
  ylab("Human − CSM divergence") +
  coord_cartesian(xlim = c(1, 3)) +
  theme_minimal(base_family = "Lora", base_size = 14) +
  theme(panel.grid.minor = element_blank(),legend.title = element_text(size = 12))
