library(tidyverse)

# Same WQX 3 query the demo's wqp_measurements call makes (demo/watershed.tape):
# USGS-03245500, exact characteristic "Specific conductance", 2025, at most 50 results.
station_id <- "USGS-03245500"
query_url <- paste0(
  "https://www.waterqualitydata.us/wqx3/Result/search",
  "?siteid=", station_id,
  "&characteristicName=Specific+conductance",
  "&startDateLo=01-01-2025&startDateHi=12-31-2025",
  "&sampleMedia=Water&mimeType=csv&zip=no&sorted=no",
  "&resultLimit=50&dataProfile=basicPhysChem"
)
retrieved_at <- format(Sys.time(), "%Y-%m-%d %H:%M %Z")

raw <- read_csv(query_url, col_types = cols(.default = col_character()))

specific_conductance <- raw %>%
  transmute(
    sample_date = as.Date(Activity_StartDate),
    value = as.numeric(Result_Measure),
    unit = Result_MeasureUnit,
    fraction = Result_SampleFraction,
    qualifier = Result_MeasureQualifierCode,
    status = Result_MeasureStatusIdentifier
  ) %>%
  mutate(
    qualifier_label = if_else(is.na(qualifier), "No qualifier/censor flag", qualifier)
  )

units <- unique(specific_conductance$unit)
stopifnot(length(units) == 1)

n_records <- nrow(specific_conductance)
date_span <- range(specific_conductance$sample_date)

plot_obj <- ggplot(
  specific_conductance,
  aes(x = sample_date, y = value, color = qualifier_label)
) +
  geom_point(size = 2.5, alpha = 0.9) +
  scale_color_manual(values = c("No qualifier/censor flag" = "#1f77b4")) +
  scale_x_date(date_labels = "%b %Y") +
  labs(
    title = "Specific conductance at USGS-03245500",
    subtitle = "Little Miami River at Milford, Ohio",
    x = "Sample / measurement date",
    y = paste0("Specific conductance (", units, ")"),
    color = "Qualification status",
    caption = paste0(
      "Data source: Water Quality Portal (WQX 3 public web services, basicPhysChem profile), ",
      "retrieved ", retrieved_at, ".\n",
      "Scope: 2025-01-01 through 2025-12-31; maximum 50 records. ", n_records,
      " returned, dated ", format(date_span[1], "%Y-%m-%d"), " to ",
      format(date_span[2], "%Y-%m-%d"), ".\n",
      "Station: ", station_id, ". Sample fraction: ",
      paste(unique(specific_conductance$fraction), collapse = ", "), "; result status: ",
      paste(unique(specific_conductance$status), collapse = ", "), ".\n",
      "Caveat: public observations only; qualifiers were absent in the returned records;\n",
      "this plot does not infer thresholds, trends, impairment, or regulatory compliance."
    )
  ) +
  theme_minimal(base_size = 12) +
  theme(
    plot.caption = element_text(hjust = 0, size = 10),
    legend.position = "bottom",
    panel.grid.minor = element_blank()
  )

output_dir <- "uat/positron/20261123"
output_file <- file.path(output_dir, "little_miami_specific_conductance_2025.png")

ggsave(
  filename = output_file,
  plot = plot_obj,
  width = 9,
  height = 6.5,
  dpi = 300
)

message("Saved plot: ", output_file, " (", n_records, " records)")

# Slide version: drawn at the deck's picture size (5.75 x 4.3 in) so its text stays
# readable; the slide text carries the scope and caveats in full.
slide_plot <- plot_obj +
  labs(
    color = NULL,
    caption = paste0(
      "Source: Water Quality Portal, WQX 3, retrieved ", format(Sys.Date()), ".\n",
      n_records, " results, none qualified. Public observations only;\n",
      "not a regulatory determination."
    )
  ) +
  theme(
    legend.position = "none",
    plot.caption = element_text(hjust = 0, size = 9)
  )

slide_file <- file.path(output_dir, "little_miami_specific_conductance_2025_slide.png")
ggsave(
  filename = slide_file,
  plot = slide_plot,
  width = 5.75,
  height = 4.3,
  dpi = 300
)

message("Saved slide plot: ", slide_file)
