1. Go to **Projects > Projects** and open or create a project.
2. Set the **Planned Date** (start and end dates) to define the planning period.
3. Navigate to the **Plan** tab.
4. Add plan lines:
   - Select a **Role/Cargo** (configure roles under **Project > Configuration > Plan Roles**)
   - Assign a **user** to the role
5. Months are generated automatically based on project dates.
6. Fill in the **Capacity (%)** for each month:
   - 0% remains neutral
   - Values > 0% are highlighted
   - Hours are calculated automatically based on company's monthly hours setting
7. Click **Generate Plan** to create/update project tasks:
   - A task is created for each plan line with non-zero capacity
   - Task name matches the role name
   - Allocated hours and planned dates are set from the plan
   - Task hour plan lines are populated with monthly distribution
8. If a task already exists with timesheets, it will not be modified.
