"""Introduction to Management Information Systems: the first non-maths course.

It proves the multi-subject machinery with three question formats code can check:
multiple choice, true/false and fill in the blank. Content follows standard
introductory MIS material (information system components, system types, relational
databases). Have a lecturer review it before real students use it.

Rules (checked for every question in app/tests/test_answers.py):
- The correct answer must not appear in the question text.
- Every misconception code used here exists in MISCONCEPTIONS.
- Multiple choice: 3-4 distinct options, exactly one correct.
"""

from typing import Any

from app.modules.curriculum.seed_ids import seed_id

BUSINESS_ID = seed_id("discipline:business")
MIS_ID = seed_id("subject:mis")
MIS_COURSE_ID = seed_id("course:intro_mis")
MIS_AREA_ID = seed_id("topic:intro_mis")
IS_BASICS_ID = seed_id("topic:is_basics")
DATABASES_ID = seed_id("topic:databases")

DISCIPLINES = [{"id": BUSINESS_ID, "name": "Business and Management", "slug": "business"}]
SUBJECTS = [
    {
        "id": MIS_ID,
        "discipline_id": BUSINESS_ID,
        "name": "Management Information Systems",
        "slug": "mis",
        "profile": "business",
    }
]
COURSES = [
    {
        "id": MIS_COURSE_ID,
        "subject_id": MIS_ID,
        "name": "Introduction to Management Information Systems",
        "level": "university",
    }
]
TOPICS = [
    {"id": MIS_AREA_ID, "parent_topic_id": None, "name": "Introduction to MIS"},
    {"id": IS_BASICS_ID, "parent_topic_id": MIS_AREA_ID, "name": "Information systems basics"},
    {"id": DATABASES_ID, "parent_topic_id": MIS_AREA_ID, "name": "Databases and data management"},
]
for _t in TOPICS:
    _t.update(subject_id=MIS_ID, course_id=MIS_COURSE_ID, grade_band="university")

PREREQUISITES = [(DATABASES_ID, IS_BASICS_ID)]

OBJECTIVES = {
    IS_BASICS_ID: [
        "Tell raw data apart from information",
        "Name the five components of an information system",
        "Match common types of information systems to the people they serve",
    ],
    DATABASES_ID: [
        "Explain what a database management system does",
        "Identify primary keys and foreign keys",
        "Explain why databases are normalised",
    ],
}

MISCONCEPTIONS: list[dict[str, Any]] = [
    {"topic_id": IS_BASICS_ID, "code": "is_volume_is_information",
     "description": "Thinks a large amount of data is information, even when it has not "
                    "been organised or summarised into something meaningful."},
    {"topic_id": IS_BASICS_ID, "code": "is_technology_only",
     "description": "Thinks an information system is only technology (hardware and "
                    "software), leaving out people, procedures and data."},
    {"topic_id": IS_BASICS_ID, "code": "is_types_level_confusion",
     "description": "Mixes up who each system serves: operational staff (TPS), middle "
                    "managers (MIS, DSS) and senior executives (ESS)."},
    {"topic_id": DATABASES_ID, "code": "db_row_column_confusion",
     "description": "Mixes up rows (records) and columns (fields)."},
    {"topic_id": DATABASES_ID, "code": "db_key_not_unique",
     "description": "Chooses or accepts a key that is not guaranteed to be unique "
                    "(names and birth dates can repeat)."},
    {"topic_id": DATABASES_ID, "code": "db_primary_foreign_confusion",
     "description": "Mixes up primary keys (identify a row in their own table) and foreign "
                    "keys (point to a row in another table)."},
    {"topic_id": DATABASES_ID, "code": "db_normalisation_purpose",
     "description": "Thinks normalisation is about speed or tidiness, rather than reducing "
                    "repeated data and the inconsistencies it causes."},
    {"topic_id": DATABASES_ID, "code": "db_many_to_many",
     "description": "Tries to represent a many-to-many relationship with one foreign key, "
                    "which only works for one-to-many."},
    {"topic_id": DATABASES_ID, "code": "db_referential_integrity",
     "description": "Does not see that a foreign key must point at a row that exists "
                    "(referential integrity)."},
]


def _mc(options: list[str], correct: int, misconceptions: dict[int, str] | None = None) -> dict:
    return {
        "kind": "multiple_choice",
        "options": options,
        "correct_index": correct,
        "misconceptions": {str(k): v for k, v in (misconceptions or {}).items()},
    }


def _tf(value: bool, misconception: str | None = None) -> dict:
    return {"kind": "true_false", "value": value, "misconception_if_wrong": misconception}


def _blank(answers: list[str], wrong: dict[str, str] | None = None) -> dict:
    return {"kind": "fill_blank", "answers": answers, "wrong_answers": wrong or {}}


_TYPES = {"multiple_choice": "multiple_choice", "true_false": "true_false",
          "fill_blank": "fill_blank"}

# (topic, objective index, difficulty, key, text, answer_data, explanation)
_QUESTIONS: list[tuple[Any, int, int, str, str, dict, str]] = [
    # --- Information systems basics ---
    (IS_BASICS_ID, 0, 1, "is_data_raw",
     "True or false: data is raw facts that have not yet been organised or given meaning.",
     _tf(True), "Data are raw facts; once organised and given meaning they become information."),
    (IS_BASICS_ID, 0, 1, "is_info_example",
     "Which of these is an example of information rather than raw data?",
     _mc(["The number 42", "A pile of unsorted sales receipts",
          "A report showing total sales per region this month", "A single customer ID"],
         2, {1: "is_volume_is_information"}),
     "A summary organised for a purpose (sales per region) is information; the receipts are "
     "still raw data, however many there are."),
    (IS_BASICS_ID, 0, 1, "is_processed_called",
     "Raw facts that have been processed and organised so they are meaningful to people "
     "are called ____.",
     _blank(["information"]), "Processing turns data into information."),
    (IS_BASICS_ID, 1, 2, "is_not_component",
     "Which of these is NOT one of the five components of an information system?",
     _mc(["Hardware", "People", "Procedures", "Profit"], 3, {1: "is_technology_only",
                                                             2: "is_technology_only"}),
     "The five components are hardware, software, data, procedures and people."),
    (IS_BASICS_ID, 1, 2, "is_people_component",
     "True or false: people are one of the components of an information system.",
     _tf(True, "is_technology_only"),
     "People use and run the system, so they are part of it, not outside it."),
    (IS_BASICS_ID, 1, 2, "is_rules_called",
     "The instructions that tell people how to use an information system are called ____.",
     _blank(["procedures", "procedure"]),
     "Procedures are the rules and instructions for operating the system."),
    (IS_BASICS_ID, 2, 3, "is_checkout_system",
     "A supermarket records every sale at the checkout. Which type of system does this?",
     _mc(["Transaction processing system (TPS)", "Executive support system (ESS)",
          "Decision support system (DSS)", "Office automation system"],
         0, {1: "is_types_level_confusion", 2: "is_types_level_confusion"}),
     "Recording routine day-to-day transactions is the job of a TPS."),
    (IS_BASICS_ID, 2, 3, "is_dss_records",
     "True or false: a decision support system mainly records day-to-day transactions.",
     _tf(False, "is_types_level_confusion"),
     "Recording transactions is a TPS job; a DSS helps analyse decisions."),
    (IS_BASICS_ID, 2, 4, "is_weekly_report",
     "A regional manager receives a weekly report comparing sales with targets. Which "
     "type of system most likely produces it?",
     _mc(["Transaction processing system (TPS)", "Management information system (MIS)",
          "Executive support system (ESS)", "Computer-aided design system"],
         1, {0: "is_types_level_confusion", 2: "is_types_level_confusion"}),
     "Routine summary reports for middle managers come from an MIS, built on TPS data."),
    (IS_BASICS_ID, 2, 4, "is_whatif_system",
     "A system that helps managers explore 'what-if' questions for decisions that are only "
     "partly structured is called a decision ____ system.",
     _blank(["support"]), "That is a decision support system (DSS)."),
    (IS_BASICS_ID, 2, 5, "is_dss_vs_ess",
     "Which statement best describes the difference between a DSS and an ESS?",
     _mc(["A DSS records transactions and an ESS stores them",
          "A DSS helps analyse specific, partly structured decisions; an ESS gives senior "
          "executives a broad, summarised view that often includes outside data",
          "They are the same system with different names",
          "An ESS is used by operational staff and a DSS by executives"],
         1, {3: "is_types_level_confusion"}),
     "DSS: focused analysis for managers. ESS: big-picture view for senior executives."),
    (IS_BASICS_ID, 1, 5, "is_feedback",
     "True or false: in an information system, feedback is output returned to people in "
     "the organisation to help them evaluate or correct the input stage.",
     _tf(True), "Feedback closes the loop from output back to input."),
    # --- Databases and data management ---
    (DATABASES_ID, 0, 1, "db_dbms_abbrev",
     "Software used to create, store, organise and retrieve the data in a database is "
     "known by a four-letter abbreviation: ____.",
     _blank(["DBMS"]), "A database management system (DBMS) manages the database."),
    (DATABASES_ID, 2, 1, "db_tables_rows",
     "True or false: in a relational database, data is stored in tables made of rows "
     "and columns.",
     _tf(True), "Relational databases organise data as tables (relations)."),
    (DATABASES_ID, 1, 1, "db_row_is",
     "In a table of students, what does one row usually represent?",
     _mc(["One student", "One column name", "The whole table", "One database"],
         0, {1: "db_row_column_confusion"}),
     "Each row (record) describes one student; each column is one attribute."),
    (DATABASES_ID, 1, 2, "db_best_pk",
     "In a table of customers, which column is the best choice for the primary key?",
     _mc(["Customer name", "City", "Customer ID", "Date of birth"],
         2, {0: "db_key_not_unique", 1: "db_key_not_unique", 3: "db_key_not_unique"}),
     "A key must be unique for every row; names, cities and birth dates can repeat."),
    (DATABASES_ID, 1, 2, "db_unique_key_called",
     "A field whose value uniquely identifies each record in its own table is called the "
     "____ key.",
     _blank(["primary"], {"foreign": "db_primary_foreign_confusion"}),
     "The primary key identifies each row of its table."),
    (DATABASES_ID, 1, 2, "db_duplicate_pk",
     "True or false: two rows in the same table may have the same primary key value.",
     _tf(False, "db_key_not_unique"), "Primary key values must be unique."),
    (DATABASES_ID, 1, 3, "db_orders_customer",
     "An Orders table has a CustomerID column that refers to rows in the Customers table. "
     "In the Orders table, CustomerID is a...",
     _mc(["Primary key", "Foreign key", "Derived attribute", "Composite index"],
         1, {0: "db_primary_foreign_confusion"}),
     "A column pointing to another table's primary key is a foreign key."),
    (DATABASES_ID, 1, 3, "db_refers_called",
     "A column that refers to the primary key of another table is called a ____ key.",
     _blank(["foreign"], {"primary": "db_primary_foreign_confusion"}),
     "That is a foreign key: it links the two tables."),
    (DATABASES_ID, 2, 4, "db_normalisation",
     "True or false: normalisation organises tables to reduce repeated (redundant) data.",
     _tf(True, "db_normalisation_purpose"),
     "Normalisation reduces redundancy and the inconsistencies it causes."),
    (DATABASES_ID, 2, 4, "db_address_every_order",
     "Storing a customer's address again in every one of their order rows mainly causes "
     "which problem?",
     _mc(["Faster queries", "Redundant data that can become inconsistent",
          "Stronger security", "A smaller database"],
         1, {0: "db_normalisation_purpose", 3: "db_normalisation_purpose"}),
     "Repeated addresses must all be updated together, or they start to disagree."),
    (DATABASES_ID, 1, 5, "db_many_to_many",
     "Students can take many courses and each course has many students. How is this "
     "relationship usually stored in a relational database?",
     _mc(["One table with repeated course columns",
          "A linking table that holds both a student key and a course key",
          "A foreign key to Courses in the Students table only",
          "A primary key made of the course name"],
         1, {0: "db_normalisation_purpose", 2: "db_many_to_many"}),
     "Many-to-many relationships need a linking (junction) table."),
    (DATABASES_ID, 1, 5, "db_fk_must_match",
     "True or false: a foreign key value must match an existing primary key value in the "
     "table it refers to (or be empty).",
     _tf(True, "db_referential_integrity"),
     "This rule is called referential integrity."),
]

QUESTIONS = [
    {
        "id": seed_id(f"question:{key}"),
        "topic_id": topic,
        "learning_objective_id": seed_id(f"objective:{topic}:{obj}"),
        "question_type": _TYPES[data["kind"]],
        "difficulty": difficulty,
        "text": text,
        "answer_data": data,
        "explanation": explanation,
        "source": "bank",
        "is_approved": True,
    }
    for topic, obj, difficulty, key, text, data, explanation in _QUESTIONS
]

LEARNING_OBJECTIVES = [
    {"id": seed_id(f"objective:{topic}:{i}"), "topic_id": topic, "text": text, "position": i}
    for topic, texts in OBJECTIVES.items()
    for i, text in enumerate(texts)
]
