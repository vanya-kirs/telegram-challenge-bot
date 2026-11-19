from app.handlers.group_reports import should_auto_delete_rejected_report, wrong_topic_report_text


def test_wrong_topic_report_text_uses_participant_name():
    text = wrong_topic_report_text("Участник А.")

    assert text.startswith("Участник А.,")
    assert "не та тема" in text
    assert "отчётов" in text


def test_duplicate_video_rejection_is_auto_deleted():
    assert should_auto_delete_rejected_report("duplicate_video") is True
    assert should_auto_delete_rejected_report("unknown_participant") is False
