from app.handlers.group_reports import should_ignore_group_message, should_process_report_message


def test_report_filter_requires_video_in_configured_group_and_topic():
    assert (
        should_process_report_message(
            chat_id=-100,
            thread_id=7,
            expected_chat_id=-100,
            expected_thread_id=7,
            has_video=True,
        )
        is True
    )
    assert (
        should_process_report_message(
            chat_id=-100,
            thread_id=7,
            expected_chat_id=-100,
            expected_thread_id=7,
            has_video=False,
        )
        is False
    )
    assert (
        should_process_report_message(
            chat_id=-200,
            thread_id=7,
            expected_chat_id=-100,
            expected_thread_id=7,
            has_video=True,
        )
        is False
    )
    assert (
        should_process_report_message(
            chat_id=-100,
            thread_id=8,
            expected_chat_id=-100,
            expected_thread_id=7,
            has_video=True,
        )
        is False
    )


def test_admin_group_messages_are_ignored():
    assert should_ignore_group_message(user_id=11, admin_ids=(11, 22)) is True
    assert should_ignore_group_message(user_id=33, admin_ids=(11, 22)) is False
    assert should_ignore_group_message(user_id=None, admin_ids=(11, 22)) is False
