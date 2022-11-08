import hashlib
import hmac
import time
import requests
import pprint
from typing import Optional
from decimal import Decimal
from urllib.parse import urljoin, urlencode
from requests.exceptions import Timeout


class ApiRequestError(Exception):
    ...

API_TIMEOUT = 4
PROXY_TYPE_SOCKS5 = 'socks5'
PROXY_TYPE_NONE = 'none'

API_KEY = ''
SECRET_KEY = ''

PROXY_TYPE = PROXY_TYPE_NONE
PROXY_HOST = ''
PROXY = ''


class BinanceClient:
    """"""

    def __init__(self, symbol: str, proxy_kind: str = None, proxy_host: str = None, proxy_port: str = None,
                 config_secret: str = None, config_key: str = None, testnet=False):
        self._symbol = symbol
        if testnet:
            self._url = 'https://testnet.binance.vision/'
        else:
            self._url = 'https://api.binance.com/'
        self._config_secret = config_secret
        self._config_key = config_key
        self._proxies = None
        if proxy_kind != PROXY_TYPE_NONE:
            socks_suffix = 'h' if proxy_kind == PROXY_TYPE_SOCKS5 else ''
            self._proxies = {
                'http': f'{proxy_kind}{socks_suffix}://{proxy_host}:{proxy_port}',
                'https': f'{proxy_kind}{socks_suffix}://{proxy_host}:{proxy_port}',
            }

    def __str__(self):
        return f'BinanceApiClient({self})'

    def _path(self, method: str) -> str:
        """ Добавляет к строке запроса требуемую команду"""
        return f'/api/v3/{method}'

    def snapshot(self) -> dict:
        """"""
        return self._send_request(
            method='get',
            path=self._path('depth'),
            params={'symbol': self._symbol.upper(), 'limit': 100},
        )

    def exchange_info(self) -> dict:
        """"""
        symbol_part = f'?symbol={self._symbol.upper()}'
        exchange_info = self._send_request('get', self._path(f'exchangeInfo{symbol_part}'))
        return exchange_info

    def trading_fee(self) -> dict:
        """ """
        return self._sign_and_send_request(
            method='get',
            path='/sapi/v1/asset/tradeFee',
            params={'symbol': self._symbol.upper()})

    def balance(self) -> dict:
        """
        https://binance-docs.github.io/apidocs/spot/en/#account-information-user_data
        """
        result = self._sign_and_send_request('get', self._path('account'))
        return {b['asset']: b['free'] for b in result['balances'] if float(b['free']) > 0}

    def new_order(self,
                  order_type: str,
                  trade_type: str,
                  quantity: Optional[Decimal],
                  order_id: str
                  ) -> dict:
        """
        https://binance-docs.github.io/apidocs/spot/en/#new-order-trade
        """
        return self._sign_and_send_request('post', self._path('order'), {
            'symbol': self._symbol,
            'side': trade_type.upper(),
            'quantity': str(quantity),
            'type': order_type.upper(),
            'newClientOrderId': order_id,
            'newOrderRespType': 'FULL'
        })

    def _signature(self, query: str) -> str:
        """"""
        return hmac.new(
            key=self._config_secret.encode(),
            msg=query.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()

    def _headers(self) -> dict:
        return {
            'X-MBX-APIKEY': self._config_key
        }

    def _send_request(self, method: str, path: str, params: Optional[dict] = None, data: Optional[dict] = None) -> dict:
        """"""
        _params = params or {}
        _data = data or {}
        full_url = urljoin(self._url, path)
        response = requests.request(
            method,
            full_url,
            params=_params,
            data=_data,
            headers=self._headers(),
            proxies=self._proxies,
            timeout=4,
        )
        if not response.ok:
            raise ApiRequestError(
                f'Request error: {response.status_code} {response.reason}, '
                f'Content: {response.content}'
            )
        return response.json()

    def _sign_and_send_request(self, method: str, path: str, params: Optional[dict] = None) -> dict:
        """"""
        p = params or {}
        p['timestamp'] = int(time.time() * 1000)
        p['signature'] = self._signature(urlencode(p))
        return self._send_request(method=method, path=path, params=p)


def get_request_size(size: Decimal, trading_settings):
    precision = int(trading_settings['symbols'][0]['quoteAssetPrecision'])
    step_size = Decimal('10') ** Decimal(-precision)
    size_filters = trading_settings['symbols'][0]['filters']
    for size_filter in size_filters:
        if size_filter['filterType'] == 'LOT_SIZE':
            step_size = Decimal(size_filter['stepSize']) if Decimal(size_filter['stepSize']) else step_size
    quantity = step_size * round(size / step_size)
    return quantity


if __name__ == '__main__':
    api_client = BinanceClient(symbol='LTCUSDT',
                                  proxy_kind=PROXY_TYPE_SOCKS5,
                                  proxy_host=PROXY_HOST,
                                  proxy_port=PROXY,
                                  config_secret=SECRET_KEY,
                                  config_key=API_KEY,
                                  testnet=False)
    try:
        message = api_client.balance()
        pprint.pprint(message)
        print('\n\n')
    except Timeout:
        print("Error Timeout balance")

    try:
        message = api_client.snapshot()
        pprint.pprint(message)
        print('\n\n')
    except Timeout:
        print("Error Timeout snapshot")


    trading_settings = api_client.exchange_info()
    pprint.pprint(trading_settings)
    print('\n\n')

    trading_fee = api_client.trading_fee()
    pprint.pprint(trading_fee)
    print('\n\n')


    quantity = get_request_size(Decimal('0.0009011111111111111111111111'), trading_settings)

    try:
        message = api_client.new_order(order_type='MARKET',
                                       trade_type='BUY',
                                       quantity=quantity,
                                       order_id='2149043174170888437')
        pprint.pprint(message)
    except ApiRequestError as er:
        print(f'Order request error: {er}')