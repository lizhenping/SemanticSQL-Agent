from models.knowledge import ColumnInfo, TableInfo, SchemaMetadata
from models.synthesis import Question
from tools.synthesis.question_synth import QuestionSynthTool
from tools.synthesis.sql_synth import SQLSynthTool
from tools.diagnosis.diagnose import DiagnoseTool

schema = SchemaMetadata(
    database_name="smoke",
    tables=[
        TableInfo(
            name="Meetings",
            row_count=2,
            columns=[
                ColumnInfo(
                    name="billable_yn",
                    data_type="TEXT",
                    sample_values=["0", "1"],
                )
            ],
        )
    ],
)

qtool = object.__new__(QuestionSynthTool)
qtool.kbase = None
qctx = qtool._build_tables_context(schema)
assert qctx[0]["columns"][0]["sample_values"] == ["0", "1"]

stool = object.__new__(SQLSynthTool)
stool.kbase = None
sctx = stool._build_context(schema, Question(question_id="q", text="x"))
assert sctx["schema_info"]["tables"]["Meetings"]["columns"][0]["sample_values"] == ["0", "1"]
enhanced = stool._build_enhanced_context(Question(question_id="q"), sctx)
assert "0, 1" in enhanced

class FakeKnowledgeBase:
    def get_domain(self):
        return None

    def get_table_names(self):
        return ["Meetings"]

    def get_column(self, *args):
        return None

    def get_field_type(self, *args):
        return None

    def get_table_semantic(self, *args):
        return None

    def get_relations(self):
        return []

    def get_schema(self):
        return schema


dtool = object.__new__(DiagnoseTool)
dtool.kbase = FakeKnowledgeBase()
dtool.ast_parser = type(
    "Parser",
    (),
    {
        "extract_tables": lambda self, sql: ["Meetings"],
        "extract_columns": lambda self, sql: [("Meetings", "billable_yn")],
    },
)()
digest = dtool._kb_digest("SELECT billable_yn FROM Meetings")
assert "Meetings.billable_yn: 0, 1" in digest
assert "not a complete domain" in digest

print("offline smoke: PASS")
