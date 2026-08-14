# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

CLASSIFICATION_SELECTION = [
    ("rfi", "Design Query (RFI/TQ)"),
    ("observation", "Minor Observation"),
    ("punch_list", "Incomplete Work (Punch List)"),
    ("nc", "Confirmed Deviation (NC/RNC)"),
    ("stop_work", "Critical Risk (Stop Work)"),
]

WORK_DIVISION_SELECTION = [
    ("preliminary", "Preliminary Works and Support"),
    ("infrastructure", "Infrastructure"),
    ("superstructure", "Superstructure"),
    ("finishing", "Enclosures, Roofing and Finishes"),
    ("installations", "Building Installations and Utilities"),
    ("equipment", "Permanent Equipment and Systems"),
    ("urbanization", "Urbanization and External Works"),
    ("other", "Other"),
]

DISCIPLINE_SELECTION = [
    ("civil", "Civil"),
    ("structure", "Structure"),
    ("architecture", "Architecture"),
    ("electrical", "Electrical"),
    ("mechanical", "Mechanical"),
    ("plumbing", "Plumbing"),
    ("hvac", "HVAC"),
    ("other", "Other"),
]

DISPOSITION_SELECTION = [
    ("correct", "Correct"),
    ("redo", "Redo"),
    ("repair", "Repair"),
    ("concession", "Request Concession"),
    ("conclude", "Conclude without Intervention"),
    ("other", "Other"),
]
