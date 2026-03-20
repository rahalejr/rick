library(jsonlite)
library(dplyr)
library(tidyr)
library(readr)
library(stringr)


fit_df <- fromJSON("noise_calibration.json", flatten = TRUE) |>
  as_tibble() |>
  transmute(
    participant = confidence,
    across(starts_with("noise_"))
  )

overall_fit <- fit_df |>
  summarise(
    across(
      starts_with("noise_"),
      \(x) sqrt(mean((participant - x)^2, na.rm = TRUE))
    )
  ) |>
  pivot_longer(
    cols = everything(),
    names_to = "noise_label",
    values_to = "rmse"
  ) |>
  mutate(
    noise_value = parse_number(noise_label)
  ) |>
  arrange(rmse)

overall_fit
