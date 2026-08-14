There are two ways to fill the plan.

**From dates and allocated time**

1. Open a task and set **Allocated Time**, **Planned Start Date** and
   **Planned End Date**.
2. Open the **Hour Plan** tab. One line per calendar month is created,
   with hours split evenly.
3. Edit the hours on any month to redistribute the effort, or edit
   **Capacity (%)** to set how much of one resource's monthly hours
   that month should take (default 160 h, configurable in *Project >
   Configuration > Settings*). Changing the percentage recalculates the
   planned hours for that month. The original equal split is kept until
   you press **Reset equal split**. Monthly values use the same
   timesheet encoding unit as the task (hours or days). The database
   always stores hours.

**From the hour plan**

1. Open a task and go to the **Hour Plan** tab without filling planned
   dates or allocated time.
2. Add one line per month. Pick the **Month**; **From** and **To** are
   always the first and last day of that month. A new line defaults to
   the next calendar month. Set hours or capacity on each line.
3. Saving the lines sets **Allocated Time** to the sum of hours and
   **Planned Start / End** to the earliest From and latest To. Further
   edits to those lines keep allocated time and planned dates in sync.
   If the plan was generated from dates instead, editing hours only
   redistributes the effort and shows a difference until the totals
   match again.

Use *Project > Reporting > Task Hour Plans* to pivot hours by month,
project and task.
