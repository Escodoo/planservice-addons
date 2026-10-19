This module adds a **Plan** tab to the project form with a matrix view for planning resources by month.

**Key features:**

- Configurable roles list (e.g., Project Manager, Architect, Assistant)
- Plan matrix with rows (role + assigned user) and columns (months)
- Automatic month generation based on project start and end dates
- Capacity percentage per cell (0% = neutral, >0% = highlighted)
- "Generate Plan" button to create/update project tasks from the plan
- Integration with existing Task Hour Plan module
- The plan can only be changed while the project is in a stage that allows
  re-planning (the module adds the **Planning** stage, where new projects
  start). In other stages the buttons are hidden and the matrix is read-only.
- Generate Plan always rewrites the task hour plans from the matrix, including
  hand-made changes; logged timesheets are never changed.

**Project settings changed on install:** the module turns **Milestones** off
and **Project Stages** on, through the regular project settings.
