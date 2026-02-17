from datetime import datetime
from freezegun import freeze_time
from pycamp_bot.models import Pycampista, Pycamp, PycampistaAtPycamp, WizardAtPycamp
from pycamp_bot.commands.wizard import (
    become_wizard, list_wizards, summon_wizard, schedule_wizards,
    show_wizards_schedule, format_wizards_schedule,
    persist_wizards_schedule_in_db, aux_resolve_show_all,
)
from test.conftest import (
    use_test_database, use_test_database_async, test_db, MODELS,
    make_update, make_message, make_context,
)


def setup_module(module):
    test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
    test_db.connect()


def teardown_module(module):
    test_db.drop_tables(MODELS)
    test_db.close()


class TestBecomeWizard:

    @use_test_database_async
    async def test_registers_user_as_wizard(self):
        p = Pycamp.create(
            headquarters="Narnia", active=True,
            init=datetime(2024, 6, 20), end=datetime(2024, 6, 23),
        )
        update = make_update(text="/ser_magx", username="gandalf")
        context = make_context()
        await become_wizard(update, context, pycamp=p)
        wizard = Pycampista.get(Pycampista.username == "gandalf")
        assert wizard.wizard is True
        assert "registrado como magx" in context.bot.send_message.call_args[1]["text"]


class TestListWizards:

    @use_test_database_async
    async def test_lists_registered_wizards(self):
        p = Pycamp.create(
            headquarters="Narnia", active=True,
            init=datetime(2024, 6, 20), end=datetime(2024, 6, 23),
        )
        p.add_wizard("gandalf", "111")
        p.add_wizard("merlin", "222")
        update = make_update(text="/ver_magx", username="admin1")
        context = make_context()
        await list_wizards(update, context, pycamp=p)
        text = context.bot.send_message.call_args[1]["text"]
        assert "@gandalf" in text
        assert "@merlin" in text


class TestSummonWizard:

    @use_test_database_async
    @freeze_time("2024-06-21 15:30:00")
    async def test_summons_current_wizard(self):
        p = Pycamp.create(
            headquarters="Narnia", active=True,
            init=datetime(2024, 6, 20), end=datetime(2024, 6, 23),
        )
        w = p.add_wizard("gandalf", "111")
        persist_wizards_schedule_in_db(p)

        update = make_update(text="/evocar_magx", username="pepe")
        context = make_context()
        await summon_wizard(update, context, pycamp=p)
        # Debe haber enviado un PING al wizard
        sent_texts = [call[1]["text"] for call in context.bot.send_message.call_args_list]
        assert any("PING" in t or "magx" in t.lower() for t in sent_texts)

    @use_test_database_async
    async def test_no_wizard_scheduled(self):
        p = Pycamp.create(
            headquarters="Narnia", active=True,
            init=datetime(2024, 6, 20), end=datetime(2024, 6, 23),
        )
        update = make_update(text="/evocar_magx", username="pepe")
        context = make_context()
        await summon_wizard(update, context, pycamp=p)
        text = context.bot.send_message.call_args[1]["text"]
        assert "No hay" in text

    @use_test_database_async
    @freeze_time("2024-06-21 15:30:00")
    async def test_wizard_summons_self(self):
        p = Pycamp.create(
            headquarters="Narnia", active=True,
            init=datetime(2024, 6, 20), end=datetime(2024, 6, 23),
        )
        w = p.add_wizard("gandalf", "111")
        persist_wizards_schedule_in_db(p)

        update = make_update(text="/evocar_magx", username="gandalf")
        context = make_context()
        await summon_wizard(update, context, pycamp=p)
        sent_texts = [call[1]["text"] for call in context.bot.send_message.call_args_list]
        assert any("sombrero" in t for t in sent_texts)


class TestScheduleWizards:

    @use_test_database_async
    async def test_schedules_and_persists(self):
        Pycampista.create(username="admin1", admin=True)
        p = Pycamp.create(
            headquarters="Narnia", active=True,
            init=datetime(2024, 6, 20), end=datetime(2024, 6, 23),
        )
        p.add_wizard("gandalf", "111")
        update = make_update(text="/agendar_magx", username="admin1")
        context = make_context()
        await schedule_wizards(update, context, pycamp=p)
        assert WizardAtPycamp.select().where(WizardAtPycamp.pycamp == p).count() > 0


class TestFormatWizardsSchedule:

    @use_test_database
    def test_formats_agenda(self):
        p = Pycamp.create(
            headquarters="Narnia",
            init=datetime(2024, 6, 20), end=datetime(2024, 6, 23),
        )
        w = Pycampista.create(username="gandalf", wizard=True)
        WizardAtPycamp.create(
            pycamp=p, wizard=w,
            init=datetime(2024, 6, 21, 9, 0),
            end=datetime(2024, 6, 21, 10, 0),
        )
        agenda = WizardAtPycamp.select().where(WizardAtPycamp.pycamp == p)
        msg = format_wizards_schedule(agenda)
        assert "Agenda de magxs" in msg
        assert "@gandalf" in msg
        assert "09:00" in msg


class TestAuxResolveShowAll:

    @use_test_database_async
    async def test_no_parameter_returns_false(self):
        msg = make_message(text="/ver_agenda_magx")
        assert aux_resolve_show_all(msg) is False

    @use_test_database_async
    async def test_completa_returns_true(self):
        msg = make_message(text="/ver_agenda_magx completa")
        assert aux_resolve_show_all(msg) is True

    @use_test_database_async
    async def test_wrong_parameter_raises(self):
        import pytest
        msg = make_message(text="/ver_agenda_magx basura")
        with pytest.raises(ValueError):
            aux_resolve_show_all(msg)
