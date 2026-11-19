def test_application_modules_import():
    import app.bot
    import app.main
    import app.scheduler
    import app.handlers.admin
    import app.handlers.group_reports
    import app.handlers.payments
    import app.handlers.registration

    assert app.bot is not None
