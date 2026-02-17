"""Tests para handlers de schedule.py: /cronogramear, /cronograma, /cambiar_slot."""
from telegram.ext import ConversationHandler
from pycamp_bot.models import Pycampista, Pycamp, Slot, Project, Vote
from pycamp_bot.commands.schedule import (
    define_slot_days, define_slot_ammount, define_slot_times, create_slot,
    make_schedule, show_schedule, change_slot, cancel, check_day_tab,
    DAY_SLOT_TIME,
)
from test.conftest import (
    use_test_database_async, test_db, MODELS,
    make_update, make_context,
)


def setup_module(module):
    test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
    test_db.connect()


def teardown_module(module):
    test_db.drop_tables(MODELS)
    test_db.close()


class TestCancel:

    @use_test_database_async
    async def test_cancel_returns_end(self):
        update = make_update(text="/cancel")
        context = make_context()
        result = await cancel(update, context)
        assert result == ConversationHandler.END
        assert "cancelado" in context.bot.send_message.call_args[1]["text"]


class TestDefineSlotDays:

    @use_test_database_async
    async def test_starts_conversation_when_ready(self):
        """Con proyectos y votos pero sin slots, inicia la conversación."""
        Pycampista.create(username="admin1", admin=True)
        owner = Pycampista.get(Pycampista.username == "admin1")
        project = Project.create(name="Proj1", owner=owner, topic="test")
        Vote.create(
            project=project, pycampista=owner, interest=True,
            _project_pycampista_id=f"{project.id}-{owner.id}",
        )
        update = make_update(text="/cronogramear", username="admin1")
        context = make_context()
        result = await define_slot_days(update, context)
        assert result == 1
        assert "dias" in context.bot.send_message.call_args[1]["text"].lower()

    @use_test_database_async
    async def test_rejects_when_schedule_exists(self):
        Pycampista.create(username="admin1", admin=True)
        Slot.create(code="A1", start=9)
        update = make_update(text="/cronogramear", username="admin1")
        context = make_context()
        result = await define_slot_days(update, context)
        assert result is None
        assert "ya existe" in context.bot.send_message.call_args[1]["text"]

    @use_test_database_async
    async def test_rejects_when_no_projects(self):
        Pycampista.create(username="admin1", admin=True)
        update = make_update(text="/cronogramear", username="admin1")
        context = make_context()
        result = await define_slot_days(update, context)
        assert result is None
        assert "No hay proyectos" in context.bot.send_message.call_args[1]["text"]

    @use_test_database_async
    async def test_rejects_when_no_votes(self):
        Pycampista.create(username="admin1", admin=True)
        owner = Pycampista.get(Pycampista.username == "admin1")
        Project.create(name="Proj1", owner=owner, topic="test")
        update = make_update(text="/cronogramear", username="admin1")
        context = make_context()
        result = await define_slot_days(update, context)
        assert result is None
        assert "votacion" in context.bot.send_message.call_args[1]["text"]

    @use_test_database_async
    async def test_non_admin_is_blocked(self):
        Pycampista.create(username="user1", admin=False)
        update = make_update(text="/cronogramear", username="user1")
        context = make_context()
        result = await define_slot_days(update, context)
        assert "No estas Autorizadx" in context.bot.send_message.call_args[1]["text"]


class TestDefineSlotAmmount:

    @use_test_database_async
    async def test_valid_day_count_returns_state_2(self):
        update = make_update(text="3")
        context = make_context()
        result = await define_slot_ammount(update, context)
        assert result == 2
        assert DAY_SLOT_TIME['day'] == ['A', 'B', 'C']

    @use_test_database_async
    async def test_invalid_day_count_returns_state_1(self):
        update = make_update(text="99")
        context = make_context()
        result = await define_slot_ammount(update, context)
        assert result == 1

    @use_test_database_async
    async def test_zero_is_invalid(self):
        update = make_update(text="0")
        context = make_context()
        result = await define_slot_ammount(update, context)
        assert result == 1


class TestDefineSlotTimes:

    @use_test_database_async
    async def test_sets_slot_count_returns_state_3(self):
        DAY_SLOT_TIME['day'] = ['A', 'B']
        update = make_update(text="4")
        context = make_context()
        result = await define_slot_times(update, context)
        assert result == 3
        assert DAY_SLOT_TIME['slot'] == ["4"]


class TestCreateSlot:

    @use_test_database_async
    async def test_creates_slots_for_day_and_moves_to_next(self):
        """Con 2 días, crear slots del primero y retornar estado 2 para el segundo."""
        DAY_SLOT_TIME['day'] = ['A', 'B']
        DAY_SLOT_TIME['slot'] = ["3"]
        update = make_update(text="9", username="admin1", chat_id=67890)
        context = make_context()
        result = await create_slot(update, context)
        # Debe retornar 2 para preguntar slots del día B
        assert result == 2
        # Se crearon 3 slots con código A1, A2, A3
        assert Slot.select().where(Slot.code.startswith("A")).count() == 3

    @use_test_database_async
    async def test_creates_slots_for_last_day_ends_conversation(self):
        """Con solo un día restante, crear slots y terminar."""
        DAY_SLOT_TIME['day'] = ['A']
        DAY_SLOT_TIME['slot'] = ["2"]
        update = make_update(text="10", username="admin1", chat_id=67890)
        context = make_context()
        result = await create_slot(update, context)
        assert result == ConversationHandler.END
        assert "Asignados" in context.bot.send_message.call_args_list[0][1]["text"]


class TestShowSchedule:

    @use_test_database_async
    async def test_shows_schedule_with_projects(self):
        owner = Pycampista.create(username="pepe")
        slot_a1 = Slot.create(code="A1", start=9)
        slot_a2 = Slot.create(code="A2", start=10)
        Project.create(name="Proyecto1", owner=owner, topic="test", slot=slot_a1)
        Project.create(name="Proyecto2", owner=owner, topic="test", slot=slot_a2)
        # Necesitamos un pycamp activo para get_slot_weekday_name
        import datetime as dt
        Pycamp.create(
            headquarters="Narnia", active=True,
            init=dt.datetime(2024, 6, 20),  # Jueves
        )
        update = make_update(text="/cronograma")
        context = make_context()
        await show_schedule(update, context)
        text = context.bot.send_message.call_args[1]["text"]
        assert "Proyecto1" in text or "Proyecto2" in text

    @use_test_database_async
    async def test_shows_empty_schedule(self):
        update = make_update(text="/cronograma")
        context = make_context()
        await show_schedule(update, context)
        # Sin slots ni proyectos, envía mensaje vacío
        context.bot.send_message.assert_called_once()


class TestChangeSlot:

    @use_test_database_async
    async def test_changes_project_slot(self):
        Pycampista.create(username="admin1", admin=True)
        owner = Pycampista.get(Pycampista.username == "admin1")
        slot_a1 = Slot.create(code="A1", start=9)
        slot_b1 = Slot.create(code="B1", start=10)
        Project.create(name="MiProyecto", owner=owner, topic="test", slot=slot_a1)
        update = make_update(text="/cambiar_slot MiProyecto B1", username="admin1")
        context = make_context()
        await change_slot(update, context)
        proj = Project.get(Project.name == "MiProyecto")
        assert proj.slot_id == slot_b1.id
        assert "Exito" in context.bot.send_message.call_args[1]["text"]

    @use_test_database_async
    async def test_rejects_missing_params(self):
        Pycampista.create(username="admin1", admin=True)
        update = make_update(text="/cambiar_slot", username="admin1")
        context = make_context()
        await change_slot(update, context)
        assert "formato" in context.bot.send_message.call_args[1]["text"].lower()

    @use_test_database_async
    async def test_nonexistent_project_or_slot(self):
        Pycampista.create(username="admin1", admin=True)
        update = make_update(text="/cambiar_slot Fantasma Z9", username="admin1")
        context = make_context()
        await change_slot(update, context)
        assert "no estan en la db" in context.bot.send_message.call_args[1]["text"]

    @use_test_database_async
    async def test_non_admin_is_blocked(self):
        Pycampista.create(username="user1", admin=False)
        update = make_update(text="/cambiar_slot Proj A1", username="user1")
        context = make_context()
        await change_slot(update, context)
        assert "No estas Autorizadx" in context.bot.send_message.call_args[1]["text"]


class TestCheckDayTab:

    @use_test_database_async
    async def test_appends_day_name_on_first_slot(self):
        import datetime as dt
        Pycamp.create(
            headquarters="Narnia", active=True,
            init=dt.datetime(2024, 6, 20),  # Jueves
        )
        slot = Slot.create(code="A1", start=9)
        cronograma = []
        await check_day_tab(slot, None, cronograma)
        assert len(cronograma) == 1
        assert "Jueves" in cronograma[0]

    @use_test_database_async
    async def test_appends_separator_and_name_on_day_change(self):
        import datetime as dt
        Pycamp.create(
            headquarters="Narnia", active=True,
            init=dt.datetime(2024, 6, 20),  # Jueves
        )
        slot_a = Slot.create(code="A1", start=9)
        slot_b = Slot.create(code="B1", start=9)
        cronograma = []
        await check_day_tab(slot_a, None, cronograma)
        await check_day_tab(slot_b, slot_a, cronograma)
        # Debe haber: nombre día A, separador vacío, nombre día B
        assert len(cronograma) == 3
        assert cronograma[1] == ''
