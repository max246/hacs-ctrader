"""cTrader API Client using asyncio TCP + ProtoBuf (ctrader-open-api messages)."""
import asyncio
import logging
import struct
import time
from typing import Any, Dict, List, Optional

from ctrader_open_api import Protobuf, EndPoints
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import ProtoMessage
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAApplicationAuthReq,
    ProtoOAApplicationAuthRes,
    ProtoOAAccountAuthReq,
    ProtoOAAccountAuthRes,
    ProtoOATraderReq,
    ProtoOATraderRes,
    ProtoOAReconcileReq,
    ProtoOAReconcileRes,
    ProtoOAGetDealListReq,
    ProtoOAGetDealListRes,
    ProtoOARefreshTokenReq,
    ProtoOARefreshTokenRes,
)

_LOGGER = logging.getLogger(__name__)

DEMO_HOST = EndPoints.PROTOBUF_DEMO_HOST
LIVE_HOST = EndPoints.PROTOBUF_LIVE_HOST
PORT = EndPoints.PROTOBUF_PORT

CTRADER_TOKEN_URL = "https://openapi.ctrader.com/apps/token"


class CTraderProtoClient:
    """Asyncio-native TCP client for cTrader ProtoBuf API."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._msg_id = 1
        self._listener_task: Optional[asyncio.Task] = None

    async def connect(self):
        """Open TCP connection to cTrader."""
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port, ssl=True)
        self._listener_task = asyncio.create_task(self._listen())
        _LOGGER.debug(f"Connected to {self.host}:{self.port}")

    async def disconnect(self):
        """Close TCP connection."""
        if self._listener_task:
            self._listener_task.cancel()
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()

    def _next_id(self) -> int:
        mid = self._msg_id
        self._msg_id += 1
        return mid

    async def send(self, request_msg, timeout: int = 10) -> Any:
        """Send a ProtoBuf message and await the response."""
        msg_id = self._next_id()

        # Wrap in ProtoMessage envelope
        proto_msg = ProtoMessage()
        proto_msg.payloadType = request_msg.payloadType
        proto_msg.payload = request_msg.SerializeToString()
        proto_msg.clientMsgId = str(msg_id)

        data = proto_msg.SerializeToString()
        # Frame: 4-byte big-endian length prefix
        frame = struct.pack(">I", len(data)) + data

        fut = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = fut

        self._writer.write(frame)
        await self._writer.drain()

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise TimeoutError(f"No response for msg_id={msg_id}")

    async def _listen(self):
        """Background task: read frames and resolve pending futures."""
        try:
            while True:
                # Read 4-byte length prefix
                raw_len = await self._reader.readexactly(4)
                length = struct.unpack(">I", raw_len)[0]
                raw_data = await self._reader.readexactly(length)

                proto_msg = ProtoMessage()
                proto_msg.ParseFromString(raw_data)

                msg_id = int(proto_msg.clientMsgId) if proto_msg.clientMsgId else None
                if msg_id and msg_id in self._pending:
                    self._pending.pop(msg_id).set_result(proto_msg)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            _LOGGER.error(f"Listener error: {e}")
            # Resolve all pending futures with exception
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(e)
            self._pending.clear()


class CTraderAPI:
    """High-level cTrader API — handles auth + data queries."""

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        account_id: str,
        client_id: str,
        client_secret: str,
        environment: str = "demo",
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.account_id = int(account_id)
        self.client_id = client_id
        self.client_secret = client_secret
        self.host = DEMO_HOST if environment == "demo" else LIVE_HOST
        self.token_expiry: float = time.time() + (30 * 24 * 60 * 60)

    async def _run(self, coro):
        """Connect, authenticate, run a coroutine, disconnect."""
        client = CTraderProtoClient(self.host, PORT)
        try:
            await client.connect()

            # App auth
            req = ProtoOAApplicationAuthReq()
            req.clientId = self.client_id
            req.clientSecret = self.client_secret
            await client.send(req)

            # Account auth
            req = ProtoOAAccountAuthReq()
            req.ctidTraderAccountId = self.account_id
            req.accessToken = self.access_token
            await client.send(req)

            return await coro(client)
        finally:
            await client.disconnect()

    async def async_get_balance(self) -> Optional[Dict[str, Any]]:
        """Fetch account balance."""
        async def _fetch(client):
            req = ProtoOATraderReq()
            req.ctidTraderAccountId = self.account_id
            msg = await client.send(req)
            res = Protobuf.extract(msg)
            trader = res.trader
            divisor = 10 ** trader.moneyDigits
            return {
                "balance": round(trader.balance / divisor, 2),
                "equity": round(getattr(trader, "equity", trader.balance) / divisor, 2),
                "margin_used": round(getattr(trader, "usedMargin", 0) / divisor, 2),
                "currency": "USD",
                "leverage": trader.leverageInCents // 100,
                "login": trader.traderLogin,
            }
        try:
            return await self._run(_fetch)
        except Exception as e:
            _LOGGER.error(f"get_balance error: {e}")
            return None

    async def async_get_open_trades(self) -> List[Dict]:
        """Fetch open positions."""
        async def _fetch(client):
            # Resolve symbol names
            from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOASymbolsListReq
            sym_req = ProtoOASymbolsListReq()
            sym_req.ctidTraderAccountId = self.account_id
            sym_msg = await client.send(sym_req)
            sym_res = Protobuf.extract(sym_msg)
            symbol_map = {int(s.symbolId): s.symbolName for s in sym_res.symbol}

            req = ProtoOAReconcileReq()
            req.ctidTraderAccountId = self.account_id
            msg = await client.send(req)
            res = Protobuf.extract(msg)

            trades = []
            for pos in res.position:
                side = "BUY" if pos.tradeData.tradeSide == 1 else "SELL"
                sym = symbol_map.get(int(pos.tradeData.symbolId), f"sym{pos.tradeData.symbolId}")
                trades.append({
                    "id": pos.positionId,
                    "symbol": sym,
                    "side": side,
                    "volume": int(pos.tradeData.volume) / 100,
                    "entry_price": round(pos.price, 5),
                    "stop_loss": round(pos.stopLoss, 5) if pos.stopLoss else None,
                    "take_profit": round(pos.takeProfit, 5) if pos.takeProfit else None,
                })
            return trades
        try:
            return await self._run(_fetch)
        except Exception as e:
            _LOGGER.error(f"get_open_trades error: {e}")
            return []

    async def async_get_closed_trades(self, limit: int = 20) -> List[Dict]:
        """Fetch recent closed deals."""
        async def _fetch(client):
            req = ProtoOAGetDealListReq()
            req.ctidTraderAccountId = self.account_id
            req.fromTimestamp = int((time.time() - 7 * 24 * 3600) * 1000)  # last 7 days
            req.toTimestamp = int(time.time() * 1000)
            req.maxRows = limit
            msg = await client.send(req)
            res = Protobuf.extract(msg)

            deals = []
            for deal in res.deal:
                side = "BUY" if deal.tradeSide == 1 else "SELL"
                deals.append({
                    "id": deal.dealId,
                    "symbol_id": deal.symbolId,
                    "side": side,
                    "volume": int(deal.filledVolume) / 100,
                    "entry_price": round(deal.executionPrice, 5),
                    "close_timestamp": deal.executionTimestamp,
                    "profit": round(getattr(deal, "closePositionDetail", None) and deal.closePositionDetail.grossProfit or 0, 2),
                })
            return deals
        try:
            return await self._run(_fetch)
        except Exception as e:
            _LOGGER.error(f"get_closed_trades error: {e}")
            return []

    async def async_update(self) -> Dict[str, Any]:
        """Fetch all data in one connection."""
        async def _fetch(client):
            # Balance
            req = ProtoOATraderReq()
            req.ctidTraderAccountId = self.account_id
            msg = await client.send(req)
            res = Protobuf.extract(msg)
            trader = res.trader
            divisor = 10 ** trader.moneyDigits
            balance = {
                "balance": round(trader.balance / divisor, 2),
                "equity": round(getattr(trader, "equity", trader.balance) / divisor, 2),
                "margin_used": round(getattr(trader, "usedMargin", 0) / divisor, 2),
                "currency": "USD",
                "leverage": trader.leverageInCents // 100,
            }

            # Symbol map
            from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOASymbolsListReq
            sym_req = ProtoOASymbolsListReq()
            sym_req.ctidTraderAccountId = self.account_id
            sym_msg = await client.send(sym_req)
            sym_res = Protobuf.extract(sym_msg)
            symbol_map = {int(s.symbolId): s.symbolName for s in sym_res.symbol}

            # Open positions
            rec_req = ProtoOAReconcileReq()
            rec_req.ctidTraderAccountId = self.account_id
            rec_msg = await client.send(rec_req)
            rec_res = Protobuf.extract(rec_msg)
            open_trades = []
            for pos in rec_res.position:
                side = "BUY" if pos.tradeData.tradeSide == 1 else "SELL"
                sym = symbol_map.get(int(pos.tradeData.symbolId), f"sym{pos.tradeData.symbolId}")
                open_trades.append({
                    "id": pos.positionId,
                    "symbol": sym,
                    "side": side,
                    "volume": int(pos.tradeData.volume) / 100,
                    "entry_price": round(pos.price, 5),
                    "stop_loss": round(pos.stopLoss, 5) if pos.stopLoss else None,
                    "take_profit": round(pos.takeProfit, 5) if pos.takeProfit else None,
                })

            # Closed deals (last 7 days)
            deal_req = ProtoOAGetDealListReq()
            deal_req.ctidTraderAccountId = self.account_id
            deal_req.fromTimestamp = int((time.time() - 7 * 24 * 3600) * 1000)
            deal_req.toTimestamp = int(time.time() * 1000)
            deal_req.maxRows = 20
            deal_msg = await client.send(deal_req)
            deal_res = Protobuf.extract(deal_msg)
            closed_trades = []
            for deal in deal_res.deal:
                side = "BUY" if deal.tradeSide == 1 else "SELL"
                closed_trades.append({
                    "id": deal.dealId,
                    "symbol": symbol_map.get(int(deal.symbolId), f"sym{deal.symbolId}"),
                    "side": side,
                    "volume": int(deal.filledVolume) / 100,
                    "entry_price": round(deal.executionPrice, 5),
                    "close_timestamp": deal.executionTimestamp,
                })

            return {
                "balance": balance,
                "open_trades": open_trades,
                "closed_trades": closed_trades,
            }

        try:
            return await self._run(_fetch)
        except Exception as e:
            _LOGGER.error(f"async_update error: {e}")
            return {"balance": None, "open_trades": [], "closed_trades": []}
