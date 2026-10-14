import io
import unittest
from unittest.mock import Mock
from run_host import forward_messages


class HostTest(unittest.TestCase):
    def test_closed_pipe_ends_bridge_while_chrome_stdin_is_open(self):
        disconnected=Mock()
        forward_messages(io.BytesIO(),io.BytesIO(),disconnected)
        disconnected.assert_called_once_with(0)


if __name__=='__main__':unittest.main()
