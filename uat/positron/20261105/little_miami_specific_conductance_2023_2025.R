library(tidyverse)

station_id <- "USGS-03245500"
unit_label <- "uS/cm @25C"

specific_conductance <- tibble(
  sample_date = as.Date(c(
    "2023-01-23", "2023-02-17", "2023-03-03", "2023-03-28", "2023-02-28",
    "2023-03-25", "2023-01-23", "2023-02-14", "2023-03-04", "2023-02-07",
    "2023-03-21", "2023-03-24", "2023-02-16", "2023-03-24", "2023-03-03",
    "2023-02-28", "2023-01-05", "2023-03-21", "2023-01-13", "2023-03-07",
    "2023-02-21", "2023-03-14", "2023-02-16", "2023-03-24", "2023-01-30"
  )),
  value = c(
    626, 419, 284, 466, 735,
    265, 632, 803, 256, 687,
    683, 444, 336, 326, 328,
    738, 562, 684, 424, 462,
    647, 607, 485, 290, 550
  ),
  qualifier = NA_character_,
  station_id = station_id,
  unit = unit_label,
  source = "Water Quality Portal (WQX 2 public web services)",
  retrieval_scope = "2023-01-01 through 2025-12-31; maximum 25 records",
  caveat = "Public observations only; qualifiers were absent in the returned records; no inferences about thresholds, trends, impairment, or regulatory compliance."
) %>%
  mutate(
    qualifier_label = if_else(is.na(qualifier), "No qualifier/censor flag", qualifier)
  )

plot_obj <- ggplot(
  specific_conductance,
  aes(x = sample_date, y = value, color = qualifier_label)
) +
  geom_point(size = 2.5, alpha = 0.9) +
  scale_color_manual(values = c("No qualifier/censor flag" = "#1f77b4")) +
  labs(
    title = "Specific conductance at USGS-03245500",
    subtitle = "Little Miami River at Milford, Ohio",
    x = "Sample / measurement date",
    y = "Specific conductance (uS/cm @25C)",
    color = "Qualification status",
    caption = paste(
      "Data source: Water Quality Portal (WQX 2 public web services).\n",
      "Scope: 2023-01-01 through 2025-12-31; maximum 25 records.\n",
      "Station: USGS-03245500.\n",
      "Caveat: public observations only; qualifiers were absent in the returned records; this plot does not infer thresholds, trends, impairment, or regulatory compliance."
    )
  ) +
  theme_minimal(base_size = 12) +
  theme(
    plot.caption = element_text(hjust = 0, size = 10),
    legend.position = "bottom",
    panel.grid.minor = element_blank()
  )

output_dir <- "uat/positron/20261105"
output_file <- file.path(output_dir, "little_miami_specific_conductance_2023_2025.png")

ggsave(
  filename = output_file,
  plot = plot_obj,
  width = 9,
  height = 6,
  dpi = 300
)

message("Saved plot: ", output_file)
