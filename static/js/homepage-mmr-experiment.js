/**
 * homepage-mmr-experiment.js — Re1 variant toggle for the MMR experiment.
 *
 * Reads the user's assignment for 'exp_re1_mmr_v1' from window.Experiments
 * and swaps which variant of each homepage row is visible:
 *   control   → data-mmr-variant="control" shown, treatment hidden
 *   treatment → data-mmr-variant="treatment" shown, control hidden
 *   null      → no-op (experiment draft / paused; control stays visible)
 *
 * Depends on experiments.js being loaded first (loaded via baseof.html).
 *
 * Exported on window.HomepageMMR for unit testing.
 */
(function () {
  'use strict';

  var EXP_ID = 'exp_re1_mmr_v1';

  /**
   * Apply the variant to all .mmr-row-wrap containers.
   * @param {'control'|'treatment'|null} variant
   */
  function applyVariant(variant) {
    if (!variant) return; // draft / paused — leave default (control visible)

    var wraps = document.querySelectorAll('.mmr-row-wrap');
    wraps.forEach(function (wrap) {
      var control   = wrap.querySelector('[data-mmr-variant="control"]');
      var treatment = wrap.querySelector('[data-mmr-variant="treatment"]');
      if (!control || !treatment) return;

      if (variant === 'treatment') {
        control.hidden = true;
        treatment.hidden = false;
      } else {
        // control (or any unknown variant) — keep default
        control.hidden = false;
        treatment.hidden = true;
      }
    });
  }

  function init() {
    var variant = null;
    try {
      if (window.Experiments && typeof window.Experiments.getVariant === 'function') {
        variant = window.Experiments.getVariant(EXP_ID);
      }
    } catch (e) {
      // Experiments module unavailable — degrade gracefully to control
    }
    applyVariant(variant);
  }

  // Expose for unit tests
  window.HomepageMMR = { applyVariant: applyVariant, init: init, EXP_ID: EXP_ID };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
