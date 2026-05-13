import pytest
from unittest.mock import MagicMock, patch


class TestMobileDeviceConnect:
    @patch("core.mobile_grabber.u2")
    def test_connect_auto_detect(self, mock_u2):
        from core.mobile_grabber import MobileDevice

        mock_device = MagicMock()
        mock_device.info = {"productName": "Xiaomi 14"}
        mock_device.window_size.return_value = (1080, 2400)
        mock_u2.connect.return_value = mock_device

        device = MobileDevice()
        device.connect()

        mock_u2.connect.assert_called_once_with()
        assert device.device is mock_device

    @patch("core.mobile_grabber.u2")
    def test_connect_with_serial(self, mock_u2):
        from core.mobile_grabber import MobileDevice

        mock_device = MagicMock()
        mock_device.info = {"productName": "Pixel 8"}
        mock_device.window_size.return_value = (1080, 2340)
        mock_u2.connect.return_value = mock_device

        device = MobileDevice()
        device.connect(serial="abc123")

        mock_u2.connect.assert_called_once_with("abc123")

    @patch("core.mobile_grabber.u2")
    def test_connect_failure_raises(self, mock_u2):
        from core.mobile_grabber import MobileDevice

        mock_u2.connect.side_effect = RuntimeError("no device")

        device = MobileDevice()
        with pytest.raises(RuntimeError, match="no device"):
            device.connect()


class TestMobileDeviceCheck:
    @patch("core.mobile_grabber.u2")
    def test_check_damai_foreground_true(self, mock_u2):
        from core.mobile_grabber import MobileDevice

        mock_device = MagicMock()
        mock_device.info = {"productName": "Test"}
        mock_device.window_size.return_value = (1080, 2400)
        mock_u2.connect.return_value = mock_device
        mock_device.app_current.return_value = {"package": "cn.damai"}

        device = MobileDevice()
        device.connect()
        assert device.check_damai_foreground() is True

    @patch("core.mobile_grabber.u2")
    def test_check_damai_foreground_false(self, mock_u2):
        from core.mobile_grabber import MobileDevice

        mock_device = MagicMock()
        mock_device.info = {"productName": "Test"}
        mock_device.window_size.return_value = (1080, 2400)
        mock_u2.connect.return_value = mock_device
        mock_device.app_current.return_value = {"package": "com.tencent.mm"}

        device = MobileDevice()
        device.connect()
        assert device.check_damai_foreground() is False

    @patch("core.mobile_grabber.u2")
    def test_window_size(self, mock_u2):
        from core.mobile_grabber import MobileDevice

        mock_device = MagicMock()
        mock_device.info = {"productName": "Test"}
        mock_device.window_size.return_value = (1080, 2400)
        mock_u2.connect.return_value = mock_device

        device = MobileDevice()
        device.connect()
        assert device.window_size() == (1080, 2400)


class TestMobileGrabberClickBuy:
    def test_click_buy_finds_text_button(self):
        from core.mobile_grabber import MobileGrabber

        mock_device = MagicMock()
        btn_not_found = MagicMock()
        btn_not_found.exists.return_value = False
        btn_not_found2 = MagicMock()
        btn_not_found2.exists.return_value = False
        btn_found = MagicMock()
        btn_found.exists.return_value = True

        def mock_selector(text=None, textContains=None):
            if text == "立即抢购":
                return btn_not_found
            if text == "立即购买":
                return btn_not_found2
            if text == "立即预订":
                return btn_found
            if text == "提交订单":
                found = MagicMock()
                found.exists.return_value = True
                return found
            m = MagicMock()
            m.exists.return_value = False
            return m

        mock_device.side_effect = mock_selector
        mock_device.window_size.return_value = (1080, 2400)

        grabber = MobileGrabber(max_retries=3, click_interval_ms=1, confirm_clicks=1)
        logs = []
        result = grabber.click_buy(mock_device, logs.append)
        assert result is True
        btn_found.click.assert_called()

    def test_click_buy_uses_coordinate_fallback(self):
        from core.mobile_grabber import MobileGrabber

        mock_device = MagicMock()
        call_count = {"n": 0}

        def mock_selector(text=None, textContains=None):
            m = MagicMock()
            m.exists.return_value = False
            if text == "提交订单":
                call_count["n"] += 1
                found = MagicMock()
                found.exists.return_value = call_count["n"] >= 2
                return found
            return m

        mock_device.side_effect = mock_selector
        mock_device.window_size.return_value = (1080, 2400)

        grabber = MobileGrabber(max_retries=5, click_interval_ms=1, confirm_clicks=1)
        logs = []
        result = grabber.click_buy(mock_device, logs.append)
        assert result is True
        mock_device.click.assert_called()

    def test_click_buy_fails_after_max_retries(self):
        from core.mobile_grabber import MobileGrabber

        mock_device = MagicMock()

        def mock_selector(text=None, textContains=None):
            m = MagicMock()
            m.exists.return_value = False
            return m

        mock_device.side_effect = mock_selector
        mock_device.window_size.return_value = (1080, 2400)

        grabber = MobileGrabber(max_retries=3, click_interval_ms=1, confirm_clicks=1)
        logs = []
        result = grabber.click_buy(mock_device, logs.append)
        assert result is False


class TestMobileGrabberConfirmOrder:
    def test_confirm_order_finds_text_then_coordinate_clicks(self):
        from core.mobile_grabber import MobileGrabber

        mock_device = MagicMock()
        btn_found = MagicMock()
        btn_found.exists.return_value = True

        def mock_selector(text=None, textContains=None):
            if text == "提交订单":
                return btn_found
            m = MagicMock()
            m.exists.return_value = False
            return m

        mock_device.side_effect = mock_selector
        mock_device.window_size.return_value = (1080, 2400)

        grabber = MobileGrabber(max_retries=3, click_interval_ms=1, confirm_clicks=5)
        logs = []
        result = grabber.confirm_order(mock_device, logs.append)
        assert result is True
        btn_found.click.assert_called()
        assert mock_device.click.call_count == 10

    def test_confirm_order_coordinate_only_when_text_not_found(self):
        from core.mobile_grabber import MobileGrabber

        mock_device = MagicMock()

        def mock_selector(text=None, textContains=None):
            m = MagicMock()
            m.exists.return_value = False
            return m

        mock_device.side_effect = mock_selector
        mock_device.window_size.return_value = (1080, 2400)

        grabber = MobileGrabber(max_retries=3, click_interval_ms=1, confirm_clicks=5)
        logs = []
        result = grabber.confirm_order(mock_device, logs.append)
        assert result is True
        assert mock_device.click.call_count == 10


class TestMobileGrabberRun:
    def test_run_success(self):
        from core.mobile_grabber import MobileGrabber

        mock_device = MagicMock()
        btn_found = MagicMock()
        btn_found.exists.return_value = True

        def mock_selector(text=None, textContains=None):
            if text in ("立即抢购", "提交订单"):
                return btn_found
            m = MagicMock()
            m.exists.return_value = False
            return m

        mock_device.side_effect = mock_selector
        mock_device.window_size.return_value = (1080, 2400)

        grabber = MobileGrabber(max_retries=3, click_interval_ms=1, confirm_clicks=2)
        logs = []
        result = grabber.run(mock_device, logs.append)
        assert result.success is True
        assert result.elapsed_ms > 0
        assert any("Step 1" in msg for msg in logs)
        assert any("Step 2" in msg for msg in logs)

    def test_run_failure_when_buy_fails(self):
        from core.mobile_grabber import MobileGrabber

        mock_device = MagicMock()

        def mock_selector(text=None, textContains=None):
            m = MagicMock()
            m.exists.return_value = False
            return m

        mock_device.side_effect = mock_selector
        mock_device.window_size.return_value = (1080, 2400)

        grabber = MobileGrabber(max_retries=2, click_interval_ms=1, confirm_clicks=1)
        logs = []
        result = grabber.run(mock_device, logs.append)
        assert result.success is False
        assert "购买" in result.message
