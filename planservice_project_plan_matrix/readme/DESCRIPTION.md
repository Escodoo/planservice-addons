This module adds a **Plan** tab to the project form with a matrix view for planning resources by month.

**Key features:**

- Configurable roles list (e.g., Project Manager, Architect, Assistant)
- Plan matrix with rows (role + assigned user) and columns (months)
- Automatic month generation based on project start and end dates
- Capacity percentage per cell (0% = neutral, >0% = highlighted)
- "Generate Plan" button to create/update project tasks from the plan
- Integration with existing Task Hour Plan module
- The plan can only be changed while the project status allows re-planning
  (**Pending** by default, the status new projects get; projects without a
  status stay open). In other statuses the buttons are hidden and the matrix is
  read-only.
- Project statuses only move forward, one step at a time (no status → first
  status → next …), for every user. Once a project leaves Pending its plan
  stays locked.
- Generate Plan always rewrites the task hour plans from the matrix, including
  hand-made changes; logged timesheets are never changed.

**Changes on install:** the module turns **Milestones** off through the regular
project settings, and gives the default project statuses their Brazilian
Portuguese names, which the Project Status module does not ship.
