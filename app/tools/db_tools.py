"""
MySQL 数据库工具模块（兼容层）

业务 CRUD 已拆分至 db_user / db_experience / db_job / db_submission /
db_interview 模块，本文件保留通用辅助函数与向后兼容的 re-export。
"""

from app.tools.db_config import (  # noqa: F401  # 向后兼容 re-export
    JOBCRAFT_DB,
    _jc_config,
    get_db_config,
)
from app.tools.db_conn import (  # noqa: F401  # 供复用方与测试 import
    _parse_json,
    connect,
    execute,
    execute_lastrowid,
    query_all,
    query_one,
    query_scalar,
)

# ============================================================
# Re-export：保持向后兼容
# from app.tools.db_tools import insert_card  仍然可用
# ============================================================

from app.tools.db_user import (  # noqa: E402, F401
    create_user,
    get_user,
    get_user_by_email,
    get_user_by_username,
    update_user,
)

from app.tools.db_experience import (  # noqa: E402, F401
    _looks_like_full_resume,
    _rebuild_entry_text,
    _row_to_card,
    count_cards,
    count_search_cards,
    delete_card,
    find_card_by_company_role,
    get_card,
    get_card_version,
    get_card_versions_by_card_id,
    get_card_versions_by_source,
    get_company_research,
    insert_card,
    insert_card_version,
    list_cards,
    list_cards_paginated,
    list_full_resume_cards,
    search_cards,
    split_resume_card_by_entries,
    update_card,
    upsert_company_research,
)

from app.tools.db_job import (  # noqa: E402, F401
    delete_job_analysis,
    get_job_analysis,
    get_selected_card_ids_by_job,
    insert_job_analysis,
    list_job_analyses,
    upsert_job_mapping,
)

from app.tools.db_submission import (  # noqa: E402, F401
    delete_submission,
    get_dashboard,
    get_submission,
    get_submission_prep_count,
    get_submission_review_count,
    insert_submission,
    list_interview_records_by_submission,
    list_submissions,
    update_submission,
)

from app.tools.db_interview import (  # noqa: E402, F401
    delete_interview_qa_pair,
    delete_interview_qa_pairs_by_record,
    delete_interview_record,
    get_interview_prep_by_job,
    get_interview_record,
    insert_interview_prep,
    insert_interview_qa_pair,
    insert_interview_record,
    list_interview_qa_pairs,
    list_interview_preps,
    list_interview_records,
    update_interview_prep_drafts,
    update_interview_qa_pair_fields,
    update_interview_record_analysis,
    update_interview_record_status,
)
