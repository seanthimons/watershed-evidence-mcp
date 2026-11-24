library(dplyr)
library(ggplot2)
library(tibble)

records <- tribble(
  ~activity_date, ~activity_time, ~value, ~unit, ~station_id, ~qualifier, ~detection_condition,
  "2023-01-23", "10:44:00", "626", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-02-17", "07:54:00", "419", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-03-03", "21:24:00", "284", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-03-28", "09:54:00", "466", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-02-28", "10:10:00", "735", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-03-25", "18:54:00", "265", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-01-23", "10:10:00", "632", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-02-14", "09:54:00", "803", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-03-04", "05:54:00", "256", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-02-07", "09:54:00", "687", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-03-21", "10:30:00", "683", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-03-24", "04:54:00", "444", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-02-16", "13:34:00", "336", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-03-24", "09:44:00", "326", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-03-03", "16:44:00", "328", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-02-28", "10:34:00", "738", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-01-05", "10:44:00", "562", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-03-21", "10:34:00", "684", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-01-13", "09:44:00", "424", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-03-07", "10:04:00", "462", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-02-21", "10:04:00", "647", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-03-14", "11:34:00", "607", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-02-16", "09:24:00", "485", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-03-24", "17:24:00", "290", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_,
  "2023-01-30", "11:44:00", "550", "uS/cm @25C", "USGS-03245500", NA_character_, NA_character_
)

plot_data <- records %>%
  mutate(
    measurement_datetime = as.POSIXct(
      paste(activity_date, activity_time),
      format = "%Y-%m-%d %H:%M:%S",
      tz = "UTC"
    ),
    value = as.numeric(value),
    qualification_status = case_when(
      !is.na(qualifier) | !is.na(detection_condition) ~ "Qualified/censored",
      TRUE ~ "Unqualified"
    )
  )

source_caption <- paste0(
  "Source: Water Quality Portal (WQX2 public web services), station USGS-03245500. ",
  "Retrieval scope: Specific conductance, 2023-01-01 through 2025-12-31, maximum 25 records (bounded sample). ",
  "Caveats: Heterogeneous public contributed records; preserve identifiers/units/qualifiers/method metadata. ",
  "No inference of missing values, thresholds, trends, impairment, or regulatory compliance."
)

p <- ggplot(plot_data, aes(x = measurement_datetime, y = value)) +
  geom_line(color = "grey60", linewidth = 0.4) +
  geom_point(aes(shape = qualification_status, color = qualification_status), size = 2.2) +
  scale_color_manual(
    values = c("Unqualified" = "#2C7FB8", "Qualified/censored" = "#D95F02"),
    drop = FALSE
  ) +
  scale_shape_manual(
    values = c("Unqualified" = 16, "Qualified/censored" = 17),
    drop = FALSE
  ) +
  labs(
    title = "Specific conductance observations (bounded retrieval)",
    subtitle = "Little Miami River at Milford OH (USGS-03245500)",
    x = "Sample/measurement date-time (UTC)",
    y = "Specific conductance (uS/cm @25C)",
    color = "Record status",
    shape = "Record status",
    caption = source_caption
  ) +
  theme_minimal(base_size = 11) +
  theme(
    legend.position = "bottom",
    plot.caption = element_text(hjust = 0)
  )

ggsave(
  filename = "uat/positron/little_miami_specific_conductance_timeseries.png",
  plot = p,
  width = 11,
  height = 7,
  units = "in",
  dpi = 300
)

