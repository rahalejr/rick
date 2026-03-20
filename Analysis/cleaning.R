###     Invariant Causal Knowledge    ###
###   Randall Hale, Patricia Cheng    ###
###            12-01-2025             ###

if(!"simr" %in% rownames(installed.packages())) {install.packages("simr")}

library(tidyverse)
library(janitor)
library(lubridate)
library(stringr)
library(lmerTest)
library(performance)
library(jsonlite)
library(simr)


metadata <- fromJSON("collisions.json", simplifyVector = FALSE)

files <- list.files('ick_data/', pattern = "\\.csv$", full.names = TRUE)

rt_df <- tibble(
  participant_id = character(),
  survey_duration = numeric(),
  participant    = numeric(),
  collision      = numeric(),
  duration       = numeric(),
  last_collision = numeric(),
  RT             = numeric(),
  selection      = numeric(),
  selected_name  = character(),
  outcome_hit    = logical(),
  num_dm         = numeric(),
  condition      = character(),
  preemption     = logical(),
  baseline_RT    = numeric(),
  brt_count      = numeric(),
  brt_sd         = numeric(),
)

attribution_df <- tibble(
  participant_id = character(),
  participant    = numeric(),
  collision      = numeric(),
  duration       = numeric(),
  last_collision = numeric(),
  ball           = numeric(),
  order          = numeric(),
  attribution    = numeric(),
  selection      = numeric(),
  selected_name = character(),
  outcome_hit    = logical(),
  normative      = logical(),
  rational       = logical(),
  RT             = numeric(),
  num_dm         = numeric(),
  condition      = character(),
  preemption     = logical(),
  baseline_RT    = numeric(),
  brt_count      = numeric(),
  brt_sd         = numeric(),
)


for (i in seq_along(files)) {
  dat <- tryCatch(
    read.csv(files[i]),
    error = function(e) {
      message("Skipping file: ", i, ' ', files[i], " (", e$message, ")")
      return(NULL)
    }
  )
  
  if (is.null(dat) || ncol(dat) != 133 || !any(dat$trial_type == "test")) {
    message("Skipping file: ", i, ' ', files[i], " (", ncol(dat), " cols)")
    next
  }
  
  
  dat <- dat %>% filter(!if_any(c(select_resp.rt, stimuli_path, selection), is.na))
  
  participant_id <- toString(dat$participant[1])
  survey_duration <- round(tail(dat$begin_review.started,1) / 60)
  brts <- dat$baseline_rts[dat$baseline_rts != ""]
  parsed_brt <- unlist(lapply(brts, function(x) fromJSON(x)))
  baseline_rt <- median(parsed_brt)
  brt_sd <- round(sd(parsed_brt), 2)
  brt_count <- length(parsed_brt)
  
  dat <- dat %>% 
    filter(trial_type == "test",
           selection != "miss")
  
  for(j in seq_len(nrow(dat))) {

    rt <- dat$select_resp.rt[j]
    stim_path <- strsplit(dat$stimuli_path[j], "/")[[1]]
    base <- strsplit(stim_path[4], '\\.')[[1]][1]
    stim_ind <- ifelse(grepl("[0-9]", base),
                       as.integer(gsub("\\D", "", base)),
                       NA_integer_)
    meta <- metadata[[stim_ind]]
    selection <- dat$selection[j]
    
    values <- list(
      participant_id = participant_id,
      participant    = i,
      condition      = dat$expName[j],
      collision      = stim_ind,
      num_dm         = ceiling(stim_ind/6),
      preemption     = meta$preemption,
      duration       = meta$duration,
      last_collision = meta$last_collision,
      RT             = rt,
      baseline_RT    = baseline_rt,
      selected_name  = selection,
      selection = ifelse(
        dat$expName[1] == "causal",
        which(meta$colors == selection),
        ifelse(selection == "hit", 1, 0)
      ),
      outcome_hit    = selection %in% c('red', 'green', 'blue', 'goal'))
    
    if (!is.na(dat$conf_1.response[j])) {
      
      print(paste(i, j))
      
      sliders <- setNames(
        list(
          dat$conf_1.response[j],
          dat$conf_2.response[j],
          dat$conf_3.response[j]
        ),
        c(dat$conf_one[j], dat$conf_two[j], dat$conf_three[j])
      )
      
      x <- unlist(sliders)
      max_ball <- names(x)[which.max(x)]
      
      for (resp in seq_len(3)) {
        color <- meta$colors[[resp]]
        ind <- which(unlist(meta$order) == resp)
        judgment <- list(
          ball        = resp,
          order       = ind,
          attribution = sliders[[meta$colors[[resp]]]],
          normative   = values$selection == meta$cause_ball,
          rational    = max_ball == selection
        )
        
        att_row <- c(values, judgment)
        
        attribution_df <- attribution_df |> add_row(!!!att_row)
      }
      
    }
    
    rt_df <- rt_df |> add_row(!!!values)
  }
}

saveRDS(attribution_df, "data/cleaned/causal_attr.rds")

saveRDS(rt_df, "data/cleaned/causal_rt.rds")
