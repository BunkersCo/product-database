"""
Test suite for the ciscoeox.tasks module
"""
import datetime
import pytest
import json
import requests
from requests import Response
from app.ciscoeox import api_crawler
from app.ciscoeox import tasks
from app.ciscoeox.exception import CiscoApiCallFailed, CredentialsNotFoundException
from app.config.models import NotificationMessage
from app.config.settings import AppSettings
from app.productdb.models import Product
from django_project.celery import TaskState

pytestmark = pytest.mark.django_db

CREDENTIALS_FILE = ".cisco_api_credentials"


@pytest.fixture
def use_test_api_configuration():
    app = AppSettings()
    with open(CREDENTIALS_FILE) as f:
        content = json.loads(f.read())
    app.set_cisco_api_enabled(True)
    app.set_product_blacklist_regex("")
    app.set_cisco_eox_api_queries("")
    app.set_auto_create_new_products(True)
    app.set_periodic_sync_enabled(False)
    app.set_cisco_api_client_id(content.get("client_id", "dummy_id"))
    app.set_cisco_api_client_id(content.get("client_secret", "dummy_secret"))


@pytest.mark.usefixtures("mock_cisco_api_authentication_server")
@pytest.mark.usefixtures("use_test_api_configuration")
@pytest.mark.usefixtures("set_celery_always_eager")
@pytest.mark.usefixtures("redis_server_required")
@pytest.mark.usefixtures("import_default_vendors")
class TestExecuteTaskToSynchronizeCiscoEoxStateTask:
    def mock_api_call(sel, monkeypatch):
        # mock the underlying API call
        def mock_response():
            r = Response()
            r.status_code = 200
            with open("app/ciscoeox/tests/data/cisco_eox_response_page_1_of_1.json") as f:
                r._content = f.read().encode("utf-8")
            return r

        monkeypatch.setattr(requests, "get", lambda x, headers: mock_response())

    def test_manual_task(self, monkeypatch):
        self.mock_api_call(monkeypatch)

        # try to execute it, while no auto-sync is enabled
        app = AppSettings()
        app.set_periodic_sync_enabled(False)
        app.set_cisco_eox_api_queries("WS-C2960-*")

        task = tasks.execute_task_to_synchronize_cisco_eox_states.delay(ignore_periodic_sync_flag=True)
        expected_result = '<div style="text-align:left;"><h3>Query: WS-C2960-*</h3>The following products are ' \
                          'affected by this update:</p><ul><li>create the Product <code>WS-C2950G-48-EI-WS</code> ' \
                          'in the database</li><li>create the Product <code>WS-C2950T-48-SI-WS</code> in the ' \
                          'database</li><li>create the Product <code>WS-C2950G-24-EI</code> in the database</li>' \
                          '</ul></div>'

        assert task is not None
        assert task.status == "SUCCESS", task.traceback
        assert task.state == TaskState.SUCCESS
        assert task.info.get("status_message") == expected_result
        assert NotificationMessage.objects.count() == 1, "Task should create a Notification Message"
        assert Product.objects.count() == 3, "Three products are part of the update"

        # test no changes required
        task = tasks.execute_task_to_synchronize_cisco_eox_states.delay(ignore_periodic_sync_flag=True)
        expected_result = '<div style="text-align:left;"><h3>Query: WS-C2960-*</h3>No changes required.</div>'

        assert task is not None
        assert task.status == "SUCCESS", task.traceback
        assert task.state == TaskState.SUCCESS
        assert task.info.get("status_message") == expected_result
        assert NotificationMessage.objects.count() == 2, "Task should create a Notification Message"
        assert Product.objects.count() == 3, "Three products are part of the update"

        # test update required
        p = Product.objects.get(product_id="WS-C2950G-24-EI")
        p.eox_update_time_stamp = datetime.date(1999, 1, 1)
        p.save()

        task = tasks.execute_task_to_synchronize_cisco_eox_states.delay(ignore_periodic_sync_flag=True)
        expected_result = '<div style="text-align:left;"><h3>Query: WS-C2960-*</h3>The following products are ' \
                          'affected by this update:</p><ul><li>update the Product data for <code>WS-C2950G-24-EI' \
                          '</code></li></ul></div>'

        assert task is not None
        assert task.status == "SUCCESS", task.traceback
        assert task.state == TaskState.SUCCESS
        assert task.info.get("status_message") == expected_result
        assert NotificationMessage.objects.count() == 3, "Task should create a Notification Message"
        assert Product.objects.count() == 3, "Three products are part of the update"

    def test_manual_task_with_single_blacklist_entry(self, monkeypatch):
        self.mock_api_call(monkeypatch)

        # try to execute it, while no auto-sync is enabled
        app = AppSettings()
        app.set_periodic_sync_enabled(False)
        app.set_cisco_eox_api_queries("WS-C2960-*")
        app.set_product_blacklist_regex("WS-C2950G-24-EI")

        task = tasks.execute_task_to_synchronize_cisco_eox_states.delay(ignore_periodic_sync_flag=True)
        expected_result = '<div style="text-align:left;"><h3>Query: WS-C2960-*</h3>The following products are ' \
                          'affected by this update:</p><ul><li>create the Product <code>WS-C2950G-48-EI-WS</code> ' \
                          'in the database</li><li>create the Product <code>WS-C2950T-48-SI-WS</code> in the ' \
                          'database</li><li>Product data for <code>WS-C2950G-24-EI</code> ignored</li>' \
                          '</ul></div>'

        assert task is not None
        assert task.status == "SUCCESS", task.traceback
        assert task.state == TaskState.SUCCESS
        assert task.info.get("status_message") == expected_result
        assert NotificationMessage.objects.count() == 1, "Task should create a Notification Message"
        assert Product.objects.count() == 2

    def test_manual_task_with_multiple_blacklist_entries(self, monkeypatch):
        self.mock_api_call(monkeypatch)

        # try to execute it, while no auto-sync is enabled
        app = AppSettings()
        app.set_periodic_sync_enabled(False)
        app.set_cisco_eox_api_queries("WS-C2960-*")
        app.set_product_blacklist_regex("WS-C2950G-48-EI-WS;WS-C2950G-24-EI")

        task = tasks.execute_task_to_synchronize_cisco_eox_states.delay(ignore_periodic_sync_flag=True)
        expected_result = '<div style="text-align:left;"><h3>Query: WS-C2960-*</h3>The following products are ' \
                          'affected by this update:</p><ul><li>Product data for <code>WS-C2950G-48-EI-WS</code> ' \
                          'ignored</li><li>create the Product <code>WS-C2950T-48-SI-WS</code> in the ' \
                          'database</li><li>Product data for <code>WS-C2950G-24-EI</code> ignored</li>' \
                          '</ul></div>'

        assert task is not None
        assert task.status == "SUCCESS", task.traceback
        assert task.state == TaskState.SUCCESS
        assert task.info.get("status_message") == expected_result
        assert NotificationMessage.objects.count() == 1, "Task should create a Notification Message"
        assert Product.objects.count() == 1, "Only a single product is imported"

    def test_periodic_task_without_queries(self, monkeypatch):
        self.mock_api_call(monkeypatch)

        # test automatic trigger
        app = AppSettings()
        app.set_periodic_sync_enabled(True)
        app.set_cisco_eox_api_queries("")

        task = tasks.execute_task_to_synchronize_cisco_eox_states.delay()

        assert task is not None
        assert task.status == "SUCCESS", task.traceback
        assert task.state == TaskState.SUCCESS
        assert task.info.get("status_message") == "No Cisco EoX API queries configured."
        assert NotificationMessage.objects.count() == 1, "Task should create a Notification Message"

    def test_api_call_error(self, monkeypatch):
        # force API failure
        def mock_response():
            raise CiscoApiCallFailed("The API is broken")

        monkeypatch.setattr(api_crawler, "update_cisco_eox_database", lambda query: mock_response())

        # test automatic trigger
        app = AppSettings()
        app.set_periodic_sync_enabled(True)
        app.set_cisco_eox_api_queries("yxcz")

        task = tasks.execute_task_to_synchronize_cisco_eox_states.delay()

        assert task is not None
        assert task.status == "SUCCESS", task.traceback
        assert task.state == TaskState.SUCCESS
        assert task.info.get("status_message", None) is None
        assert task.info.get("error_message") == "Cisco EoX API call failed (The API is broken)"
        assert NotificationMessage.objects.count() == 1, "Task should create a Notification Message"

    def test_credentials_not_found(self, monkeypatch):
        # force API failure
        def mock_response():
            raise CredentialsNotFoundException("Something is wrong with the credentials handling")

        monkeypatch.setattr(api_crawler, "update_cisco_eox_database", lambda query: mock_response())

        # test automatic trigger
        app = AppSettings()
        app.set_periodic_sync_enabled(True)
        app.set_cisco_eox_api_queries("yxcz")

        task = tasks.execute_task_to_synchronize_cisco_eox_states.delay()

        assert task is not None
        assert task.status == "SUCCESS", task.traceback
        assert task.state == TaskState.SUCCESS
        assert task.info.get("status_message", None) is None
        assert task.info.get("error_message") == "Invalid credentials for Cisco EoX API or insufficient access " \
                                                 "rights (Something is wrong with the credentials handling)"
        assert NotificationMessage.objects.count() == 1, "Task should create a Notification Message"

    def test_api_check_failed(self, monkeypatch):
        # force API failure
        def mock_response():
            raise Exception("The API is broken")

        monkeypatch.setattr(requests, "get", lambda x, headers: mock_response())

        # test automatic trigger
        app = AppSettings()
        app.set_periodic_sync_enabled(True)
        app.set_cisco_eox_api_queries("yxcz")

        task = tasks.execute_task_to_synchronize_cisco_eox_states.delay()

        assert task is not None
        assert task.status == "SUCCESS", task.traceback
        assert task.state == TaskState.SUCCESS
        assert task.info.get("status_message", None) is None
        assert task.info.get("error_message") == "Cannot access the Cisco API. Please ensure that the server is " \
                                                 "connected to the internet and that the authentication settings are " \
                                                 "valid."
        assert NotificationMessage.objects.count() == 1, "Task should create a Notification Message"

    def test_periodic_task_enabled_state(self, monkeypatch):
        self.mock_api_call(monkeypatch)

        # test automatic trigger
        app = AppSettings()
        app.set_periodic_sync_enabled(False)
        task = tasks.execute_task_to_synchronize_cisco_eox_states.delay()

        assert task is not None
        assert task.status == "SUCCESS", task.traceback
        assert task.state == TaskState.SUCCESS
        assert task.info.get("status_message") == "task not enabled"

        app.set_periodic_sync_enabled(True)

        task = tasks.execute_task_to_synchronize_cisco_eox_states.delay()

        assert task is not None
        assert task.status == "SUCCESS", task.traceback
        assert task.state == TaskState.SUCCESS
        assert task.info.get("status_message") != "task not enabled"
