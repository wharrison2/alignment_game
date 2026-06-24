## Frontend
 - Can't start a game without selecting dev mode
 - All strings should be named and be in one file (later this should be i18n compatible)
 - Research items show a warning for AI assist when none is used

## Backend
 - Market caps decline/plateau the turns after a release, but should continue growing
 - Some base investment early on that falls off if you don't do anything

## UX Design
 - Off white background, serif font, clean lines, credible
 - Name your lab and choose your ticker (default first 3 characters) at the start
### Market cap graph
 - linear scale
 - hoverable lines, tickers at the edge stay fixed to the end, ticker capitalized and sans serif, ticker shape and text slightly enlarges on hover, lines slightly thicken
 - tickers sit in a tab shape (the shape that results when you concatenate an isosceles triangle with its base facing right with a rectangle whose height matches the base of the triangle with a semicircle to cap off the right edge)
 - between fixed market caps at quarters, the interim should have a slightly noisy path upwards resembling a real stock. my idea is to produce this noise by dividing the quarter into some number of steps, generating a list of numbers that adds to 0 (maybe just by going [-2, -2, -2, -1, -1, -1, 0, 0, 0, 1, 1, 1, 2, 2, 2] or something like that, length obviously manufactured), shuffling it, then making the displayed value at each step be exp(sum_trough_step(i) + i * ln(growth_factor) / num_steps) where growth_factor is the true growth in market cap between quarters. object to this if theres a significantly cleaner way.
 - dates across the bottom

### Research items
 - individual items within the set of items, not just text next to a button, click to reveal the modal
 - in progress research items have the same display in that section (ideally make a research_item class, inheritance to reflect the actual subdivisions, states for unresearched/in progress/completed) 
 - completed research should also be visible


## Training
 - Unlocks carry with them ceilings and contamination in pre and post train
 - safety and capability advances should be unlocked and determine how your training runs go
 - safety advances that affect pretraining (eg clean your data, synthetic aligned data (hugely contaminated if AI assist), you make a few more) and post training (you figure this out). Make them clear, tangible interventions -- not "better architecture" 
 - No more safety knob