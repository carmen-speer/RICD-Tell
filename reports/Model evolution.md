# Model evolution: tracker v1, v2 and the search for the meta channel

Moved from the main README on November 21, 2026, unchanged, so the README can describe the current tracker while this record stays complete. Every protocol named here is in [`protocols/`](<../protocols/>), and every error with its fix is in [`history of fixes/`](<../history of fixes/>).

## Tracker v1: not passed, and why

The first confirmatory test ([`sampling protocol.md`](<../protocols/sampling protocol.md>)) scored 278 of 300 randomly drawn institutions with a classifier trained on the 54-institution development panel. It flagged 12 of the 13 institutions that later closed or merged, but it also flagged 253 of the 278, which is no use as a warning.

Two mistakes produced that result. The first was an omitted step. The panel had been assembled to teach the tracker what different kinds of collapse look like, so nearly half of it (23 of 54) were closures, far above the real rate of about 5% over six years. Building a model on a sample enriched with rare events is a standard design (case-control sampling), but it requires a correction for the true base rate before the model scores the real population (King and Zeng, 2001, "Logistic Regression in Rare Events Data"), and that correction was omitted. The model's ranking held, catching 12 of 13 closures, but its cutoff was set for a world in which almost half of colleges fail, so it flagged almost everything in the real one. The second was the insufficient-data rule, adopted after the scores of one college (Thomas Aquinas College) would not reproduce reliably: any candidate whose records were incomplete, or whose results were unstable, was skipped and replaced. That rule passed over 476 candidates, and 54 of them later closed or merged, four times the 13 closures among the institutions actually scored. Colleges in trouble are exactly the ones whose records thin out, so the rule threw away the signal it should have been reading.

## Tracker v2: passed, narrowly

Protocol v2 ([`sampling protocol v2.md`](<../protocols/sampling protocol v2.md>)) fixed both mistakes. The classifier was trained on a random draw of 600 institutions from 2014, with their real outcomes over the next five years, so it learned the real rate of failure. And missing data became a signal instead of a reason for exclusion: two new features measure gaps in an institution's reporting (years missing at the end of its record, and years missing in between), institutions that still could not be scored were kept in the record rather than replaced, and their outcomes are reported alongside every result.

Tested on 245 scorable institutions from 2019, v2 passed (J 0.40, 95% interval 0.08 to 0.72), catching 6 of 11 closures. But it passed almost entirely by flagging for-profit colleges, which close far more often than others; among public and nonprofit colleges it caught only 1 of 6 closures.


## The search for the meta channel (exploratory)

Two hypotheses about who carries the meta channel were measured from the IPEDS staffing files and tested on the development colleges, then the first was retested on the held-out v3 colleges under a pre-registered protocol ([`administrative layer retest protocol.md`](<../protocols/administrative layer retest protocol.md>)):

- **The administrative layer.** The hypothesis: the meta layer is the administrative class, and the thicker it is, the more it spends on form rather than function, forms a firewall between official and operational values, and drives divergence and debt. Result: compared at equal size and wealth, a thicker administrative layer goes with more of the tracker's resource debt across all colleges, but it does not predict closure, and it rises together with full-time faculty rather than replacing them. Among private nonprofits, the colleges that closed most often were those with a thin administrative layer and fast-growing debt: a college too starved to hire, not one bloated with administrators. The administrative layer looks less like the meta channel than like a cost on resources in its own right.
- **Tenure protection.** The hypothesis (RICD Spine §15.2): the meta channel is the population that can transmit dissent accurately, and job security is what makes that possible, so a college with more tenure-protected faculty catches and corrects divergence. Result: compared at equal size and wealth, a higher tenure share did not predict less closure, and it went with more, not less, of the tracker's resource debt.

Both candidates point the "wrong" way against the same debt measure, the one built from sticker tuition and completion that barely predicts closure. That points to the yardstick rather than settling the candidates. A staffing share describes who makes up a college, not what its people read, so neither is used as the meta channel; its first reading, staff exit, is described under "Testing new channels," and whether staffing composition adds anything beyond it will be tested separately.

