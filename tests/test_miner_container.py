import base64
import pytest
from unittest import mock

from neurons.Miner.container import (
    run_container,
    check_container,
    pause_container,
    unpause_container,
    get_docker,
    kill_container,
    set_docker_base_size
)

# --- Autouse Fixture to Patch Module-Level Container Names ---
@pytest.fixture(autouse=True)
def patch_container_names(monkeypatch):
    """
    Ensure that module-level variables for container names are set to known values.
    This helps the functions under test to correctly match container names.
    """
    from neurons.Miner import container as cnt
    monkeypatch.setattr(cnt, "container_name", "container")
    monkeypatch.setattr(cnt, "container_name_test", "test_container")


# --- Dummy Virtual Memory for psutil ---
class DummyVirtualMemory:
    available = 8 * 1024**3  # 8 GB


# --- Fixtures for common objects ---

@pytest.fixture
def allocation_key_fixture():
    return "test_public_key"


@pytest.fixture
def mock_retrieve_allocation_key(allocation_key_fixture):
    """Returns a mock allocation key."""
    mock_retrieve = mock.MagicMock(return_value=allocation_key_fixture)
    patcher = mock.patch('neurons.Miner.container.retrieve_allocation_key', mock_retrieve)

    patcher.start()

    yield mock_retrieve

    patcher.stop()


@pytest.fixture
def mock_containers():
    return []


@pytest.fixture
def docker_client():
    return mock.MagicMock()


@pytest.fixture
def mock_get_docker(mock_containers, docker_client):
    client = docker_client
    client.containers.list = mock.MagicMock(return_value=mock_containers)
    client.images.build = mock.MagicMock(return_value=(None, None))
    client.images.prune = mock.MagicMock()

    patcher_get = mock.patch('neurons.Miner.container.get_docker', return_value=(client, mock_containers))
    patcher_from_env = mock.patch('docker.from_env', return_value=client)

    patcher_get.start()
    patcher_from_env.start()

    yield get_docker

    patcher_from_env.stop()
    patcher_get.stop()


@pytest.fixture
def running_container(mock_containers):
    """A regular container in 'running' state with expected name."""
    container = mock.MagicMock()
    container.name = "container"
    container.status = "running"
    mock_containers.append(container)
    return container


@pytest.fixture
def exited_container(mock_containers):
    """A regular container in 'exited' state with expected name."""
    container = mock.MagicMock()
    container.name = "container"
    container.status = "exited"
    mock_containers.append(container)
    return container


@pytest.fixture
def running_test_container(mock_containers):
    """A test container in 'running' state with expected test name."""
    container = mock.MagicMock()
    container.name = "test_container"
    container.status = "running"
    mock_containers.append(container)
    return container


@pytest.fixture
def other_container(mock_containers):
    """A test container in 'running' state with expected test name."""
    container = mock.MagicMock()
    container.name = "other_container"
    container.status = "running"
    mock_containers.append(container)
    return container


@pytest.fixture
def new_container(mock_containers):
    """A test container in 'running' state with expected test name."""
    container = mock.MagicMock()
    container.name = "container"
    container.status = "created"
    mock_containers.append(container)
    return container


@pytest.fixture
def mock_run_container(docker_client, new_container):
    docker_client.containers.run = mock.MagicMock(return_value=new_container)

    return new_container


@pytest.fixture
def mock_open_fn():
    patcher = mock.patch('builtins.open', new_callable=mock.mock_open())

    yield patcher.start()

    patcher.stop()


@pytest.fixture
def mock_container_build(monkeypatch):
    patcher1 = mock.patch('os.makedirs')
    patcher3 = mock.patch('neurons.Miner.container.rsa.encrypt_data', return_value=b"encrypted_data")
    patcher4 = mock.patch('neurons.Miner.container.psutil.virtual_memory', return_value=DummyVirtualMemory())
    patcher5 = mock.patch('neurons.Miner.container.build_sample_container')
    patcher6 = mock.patch('neurons.Miner.container.password_generator', return_value="testpwd")

    # Set module-level globals required by run_container.
    from neurons.Miner import container as cnt
    monkeypatch.setattr(cnt, "image_name_base", "dummy_base")
    monkeypatch.setattr(cnt, "image_name", "dummy_image")
    monkeypatch.setattr(cnt, "__version_as_int__", 1)

    patcher1.start()
    patcher3.start()
    patcher4.start()
    patcher5.start()
    patcher6.start()

    yield

    patcher6.stop()
    patcher5.stop()
    patcher4.stop()
    patcher3.stop()
    patcher1.stop()



# --- Grouped Tests ---

class TestRunContainer:
    def test_run_container_success(
        self,
        mock_container_build,
        mock_get_docker,
        docker_client,
        new_container,
        mock_run_container,
        mock_open_fn,
    ):
        """
        run_container:
        Should successfully run a new container when all dependencies are met and
        container.status is 'created'. Returns a dict with status True and the encrypted info.
        """
        # Prepare input parameters
        cpu_usage = {"assignment": "0-1"}
        ram_usage = {"capacity": "5g"}
        hard_disk_usage = {"capacity": "100g"}
        gpu_usage = {"capacity": "all"}
        public_key = "dummy_public_key"
        docker_requirement = {
            "base_image": "dummy_base",
            "volume_path": "/dummy/volume",
            "ssh_key": "dummy_ssh_key",
            "ssh_port": 2222,
            "dockerfile": ""
        }
        testing = True

        # Call run_container
        result = run_container(cpu_usage, ram_usage, hard_disk_usage, gpu_usage,
                               public_key, docker_requirement, testing)

        # Verify that the image was built and container was run.
        docker_client.images.build.assert_called_once()
        docker_client.containers.run.assert_called_once()
        # Ensure container name passed to run() is "test_container"
        _, kwargs = docker_client.containers.run.call_args
        assert kwargs.get("name") == "test_container"

        # FIXME: not sure why the first one is lost, need to fix this assert
        #mock_open_fn.assert_called_with('./tmp/dockerfile', 'w')
        mock_open_fn.assert_called_with('allocation_key', 'w')

        expected_info = base64.b64encode(b"encrypted_data").decode("utf-8")
        assert result
        assert result["status"] is True
        assert result["message"]
        assert result["info"] == expected_info


class TestCheckContainer:
    def test_check_container_running(self, mock_get_docker, running_container):
        """
        check_container:
        Returns True when a regular container (with name "container") is running.
        """
        assert check_container() is True

    def test_check_container_test_running(self, mock_get_docker, running_test_container):
        """
        check_container:
        Returns True when a test container (with name "test_container") is running.
        """
        assert check_container() is True

    def test_check_container_not_running(self, mock_get_docker, other_container):
        """
        check_container:
        Returns False when the container name does not match the expected value.
        """
        assert check_container() is False

    def test_check_container_exception(self, mock_get_docker):
        """
        check_container:
        Returns False when an exception is raised during Docker access.
        """
        mock_get_docker.side_effect = Exception("Test error")

        assert check_container() is False


class TestPauseContainer:
    def test_pause_container_success(self, mock_get_docker, mock_retrieve_allocation_key, allocation_key_fixture, running_container):
        """
        pause_container:
        Pauses the container when the allocation key is valid.
        """
        result = pause_container(allocation_key_fixture)

        running_container.pause.assert_called_once()
        assert result
        assert result["status"] is True
        assert result["message"]

    def test_pause_container_no_allocation_key(self, mock_get_docker, mock_retrieve_allocation_key, running_container):
        """
        pause_container:
        Returns False if no allocation key is retrieved.
        """
        mock_retrieve_allocation_key.return_value = None

        result = pause_container("test_public_key")

        assert result
        assert result["status"] is False
        assert result["message"] == "Failed to retrieve allocation key."

    def test_pause_container_key_mismatch(self, mock_get_docker, mock_retrieve_allocation_key):
        """
        pause_container:
        Returns False when the provided allocation key does not match.
        """
        result = pause_container("invalid_key")

        assert result
        assert result["status"] is False
        assert result["message"] == "Permission denied."

    def test_pause_container_not_found(self, mock_retrieve_allocation_key, allocation_key_fixture, mock_get_docker, running_container):
        """
        pause_container:
        Returns False when no container with the expected name is found.
        """
        running_container.name = "not_found"  # does not contain "container"
        result = pause_container(allocation_key_fixture)

        assert result
        assert result["status"] is False
        assert result["message"] == "Unable to find container"

    def test_pause_container_exception(self, mock_retrieve_allocation_key, mock_get_docker, allocation_key_fixture, running_container):
        """
        pause_container:
        Returns False when an exception occurs in get_docker.
        """
        running_container.pause = mock.MagicMock(side_effect=Exception("Test error"))

        result = pause_container(allocation_key_fixture)

        assert result
        assert result["status"] is False
        assert result["exception"] == "Exception"
        assert result["message"] == "Error pausing container Test error"
        assert result["traceback"]
        assert result["traceback"][0] == "Traceback (most recent call last):\n"
        assert result["traceback"][-1] == "Exception: Test error\n"


class TestUnpauseContainer:
    def test_unpause_container_success(self, mock_retrieve_allocation_key, mock_get_docker, allocation_key_fixture, running_container):
        """
        unpause_container:
        Unpauses the container when the allocation key is valid.
        """

        result = unpause_container(allocation_key_fixture)

        running_container.unpause.assert_called_once()
        assert result
        assert result["status"] is True
        assert result["message"]

    def test_unpause_container_no_allocation_key(self, mock_get_docker, mock_retrieve_allocation_key, running_container):
        """
        unpause_container:
        Returns False if no allocation key is retrieved.
        """
        mock_retrieve_allocation_key.return_value = None

        result = unpause_container("test_public_key")

        assert result
        assert result["status"] is False
        assert result["message"] == "Failed to retrieve allocation key."

    def test_unpause_container_key_mismatch(self, mock_get_docker, mock_retrieve_allocation_key, allocation_key_fixture):
        """
        unpause_container:
        Returns False when the provided allocation key does not match.
        """
        result = unpause_container("invalid_key")

        assert result
        assert result["status"] is False
        assert result["message"] == "Permission denied."

    def test_unpause_container_not_found(self, mock_retrieve_allocation_key, mock_get_docker, allocation_key_fixture, running_container):
        """
        unpause_container:
        Returns False when no container with the expected name is found.
        """
        running_container.name = "not_found"

        result = unpause_container(allocation_key_fixture)

        assert result
        assert result["status"] is False
        assert result["message"] == "Unable to find container"

    def test_unpause_container_exception(self, mock_retrieve_allocation_key, mock_get_docker, allocation_key_fixture, running_container):
        """
        unpause_container:
        Returns False when an exception occurs in get_docker.
        """
        running_container.unpause = mock.MagicMock(side_effect=Exception("Test error"))

        result = unpause_container(allocation_key_fixture)

        assert result
        assert result["status"] is False
        assert result["exception"] == "Exception"
        assert result["message"] == "Error unpausing container Test error"
        assert result["traceback"]
        assert result["traceback"][0] == "Traceback (most recent call last):\n"


class TestGetDocker:
    def test_get_docker_success(self, mock_get_docker, mock_containers, docker_client):
        """
        get_docker:
        Initializes the Docker client and lists containers successfully.
        """

        client, containers = get_docker()

        assert client == docker_client
        assert containers == mock_containers
        client.containers.list.assert_called_once_with(all=True)

    def test_get_docker_exception(self, mock_get_docker):
        """
        get_docker:
        Raises an exception if Docker client initialization fails.
        """
        with mock.patch('docker.from_env', side_effect=Exception("Docker error")):

            with pytest.raises(Exception):
                get_docker()

    def test_get_docker_list_exception(self, mock_get_docker, docker_client):
        """
        get_docker:
        Raises an exception if listing containers fails.
        """
        docker_client.containers.list.side_effect = Exception("List error")

        with pytest.raises(Exception):
            get_docker()


class TestKillContainer:
    def test_kill_container_test_running(self, mock_get_docker, running_test_container, docker_client):
        """
        kill_container:
        Kills a running test container.
        """

        kill_container(True)

        running_test_container.exec_run.assert_called_once_with(cmd="kill -15 1")
        running_test_container.wait.assert_called_once()
        running_test_container.remove.assert_called_once()
        docker_client.images.prune.assert_called_once_with(filters={"dangling": True})

    #@mock.patch('neurons.Miner.container.get_docker')
    def test_kill_container_test_not_running(self, mock_get_docker, docker_client, running_test_container):
        """
        kill_container:
        Removes a test container that is not running.
        """
        running_test_container.status = "exited"

        kill_container(True)

        running_test_container.exec_run.assert_not_called()
        running_test_container.wait.assert_not_called()
        running_test_container.remove.assert_called_once()
        docker_client.images.prune.assert_called_once_with(filters={"dangling": True})

    def test_kill_container_regular_running(self, mock_get_docker, docker_client, running_container):
        """
        kill_container:
        Kills a running regular container.
        """

        kill_container(True)

        running_container.exec_run.assert_called_once_with(cmd="kill -15 1")
        running_container.wait.assert_called_once()
        running_container.remove.assert_called_once()
        docker_client.images.prune.assert_called_once_with(filters={"dangling": True})

    #@mock.patch('neurons.Miner.container.get_docker')
    def test_kill_container_regular_not_running(self, mock_get_docker, docker_client, exited_container):
        """
        kill_container:
        Removes a regular container that is not running.
        """

        kill_container(True)

        exited_container.exec_run.assert_not_called()
        exited_container.wait.assert_not_called()
        exited_container.remove.assert_called_once()
        docker_client.images.prune.assert_called_once_with(filters={"dangling": True})

    def test_kill_container_deregister_false(self, mock_get_docker, docker_client, running_container, running_test_container):
        """
        kill_container:
        When deregister=False, only looks for and removes the test container.
        """

        kill_container(deregister=False)

        running_test_container.exec_run.assert_called_once_with(cmd="kill -15 1")
        running_test_container.wait.assert_called_once()
        running_test_container.remove.assert_called_once()
        running_container.exec_run.assert_not_called()
        running_container.wait.assert_not_called()
        running_container.remove.assert_not_called()
        docker_client.images.prune.assert_called_once_with(filters={"dangling": True})

    def test_kill_container_deregister_true_with_both_containers(self, mock_get_docker, docker_client, running_container, running_test_container):
        """
        kill_container:
        When deregister=True, looks for and removes both test and regular containers.
        """

        kill_container(deregister=True)

        running_test_container.exec_run.assert_called_once_with(cmd="kill -15 1")
        running_test_container.wait.assert_called_once()
        running_test_container.remove.assert_called_once()
        running_container.exec_run.assert_called_once_with(cmd="kill -15 1")
        running_container.wait.assert_called_once()
        running_container.remove.assert_called_once()
        docker_client.images.prune.assert_called_once_with(filters={"dangling": True})

    def test_kill_container_not_found(self, mock_get_docker, docker_client, other_container):
        """
        kill_container:
        Does nothing if no matching container is found.
        """

        kill_container(True)

        other_container.exec_run.assert_not_called()
        other_container.wait.assert_not_called()
        other_container.remove.assert_not_called()
        docker_client.images.prune.assert_called_once_with(filters={"dangling": True})

    def test_kill_container_exception(self, mock_get_docker, running_test_container):
        """
        kill_container:
        Returns False when get_docker raises an exception.
        """
        running_test_container.remove.side_effect = Exception("Test error")

        with pytest.raises(Exception):
            kill_container(True)


class TestSetDockerBaseSize:
    def test_set_docker_base_size(self, mock_open_fn):
        """
        set_docker_base_size:
        Verifies that the function writes the correct JSON content to /etc/docker/daemon.json
        and calls subprocess.run to restart Docker.
        """
        mock_json_dump = mock.MagicMock()
        mock_subprocess_run = mock.MagicMock()
        patcher1 = mock.patch('subprocess.run', mock_subprocess_run).start()
        patcher2 = mock.patch('json.dump', mock_json_dump).start()
        base_size = "100g"
        expected_file = "/etc/docker/daemon.json"
        expected_dict = {
            "storage-driver": "devicemapper",
            "storage-opts": ["dm.basesize=" + base_size]
        }

        set_docker_base_size(base_size)

        mock_open_fn.assert_called_once_with(expected_file, "w")
        with mock_open_fn() as file_handle:
            mock_json_dump.assert_called_once_with(expected_dict, file_handle, indent=4)
        mock_subprocess_run.assert_called_once_with(["systemctl", "restart", "docker"])
        patcher2.stop()
        patcher1.stop()
