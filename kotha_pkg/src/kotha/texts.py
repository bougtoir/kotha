"""Fixed user-visible statements. Changing them changes the result hash of new results."""
LIMITATIONS = [
    "Research use only. Not validated for individual treatment decisions.",
    "Aggregate data cannot distinguish bias in external evidence from genuine effect modification.",
    "No automatic causal transportability: compatibility statistics are not evidence of exchangeability.",
    "In the R1 simulations, the KOTHA workflow showed no net decision advantage over robust MAP combined with the same observable screen.",
    "The prespecified Stage C beneficial-borrowing threshold failed in R1 (0.4895 < 0.5).",
    "The Stage C design-credibility judgement is recorded as entered by the named assessor; the software does not verify it.",
]
EXPLORATORY_LABEL = "EXPLORATORY \u2014 not supported by recorded design judgement"
SUPPORTED_LABEL = "Conditional borrowing permitted by the recorded design judgement (judgement not verified by software)"
CONFLICT_NOTE = "Statistical prior-data conflict diagnostic only; it is not a design or causal assessment."
