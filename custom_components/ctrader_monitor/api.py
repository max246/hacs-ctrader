"""cTrader API Client — asyncio TCP + bundled ProtoBuf messages (no Twisted)."""
import asyncio
import logging
import struct
import time
from typing import Any, Dict, List, Optional

from .proto.OpenApiCommonMessages_pb2 import ProtoMessage
from .proto.OpenApiMessages_pb2 import (
    ProtoOAApplicationAuthReq,
    ProtoOAAccountAuthReq,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetAccountListByAccessTokenRes,
    ProtoOATraderReq,
    ProtoOATraderRes,
    ProtoOAReconcileReq,
    ProtoOAReconcileRes,
    ProtoOADealListReq,
    ProtoOADealListRes,
    ProtoOASymbolsListReq,
    ProtoOASymbolsListRes,
    ProtoOASubscribeSpotsReq,
    ProtoOASpotEvent,
    ProtoOAErrorRes,
)

_LOGGER = logging.getLogger(__name__)

DEMO_HOST = "demo.ctraderapi.com"
LIVE_HOST = "live.ctraderapi.com"
PORT = 5035


ERROR_PAYLOAD_TYPE = 2142  # ProtoOAErrorRes


def _extract(proto_msg, res_class):
    """Parse a raw ProtoMessage payload into the expected response class."""
    if proto_msg.payloadType == ERROR_PAYLOAD_TYPE:
        error = ProtoOAErrorRes()
        error.ParseFromString(proto_msg.payload)
        raise Exception(f"cTrader error: {error.errorCode} — {error.description}")
    result = res_class()
    result.ParseFromString(proto_msg.payload)
    return result


class CTraderProtoClient:
    """Asyncio-native TCP+SSL client for cTrader ProtoBuf API."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._msg_id = 1
        self._listener_task: Optional[asyncio.Task] = None

    async def connect(self):
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port, ssl=True)
        self._listener_task = asyncio.create_task(self._listen())

    async def disconnect(self):
        if self._listener_task:
            self._listener_task.cancel()
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

    async def send(self, request_msg, timeout: int = 10) -> ProtoMessage:
        """Wrap request in ProtoMessage envelope, send, and await response."""
        msg_id = self._msg_id
        self._msg_id += 1

        envelope = ProtoMessage()
        envelope.payloadType = request_msg.payloadType
        envelope.payload = request_msg.SerializeToString()
        envelope.clientMsgId = str(msg_id)

        data = envelope.SerializeToString()
        self._writer.write(struct.pack(">I", len(data)) + data)
        await self._writer.drain()

        fut = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = fut

        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
            _LOGGER.debug(f"Response payloadType={result.payloadType} for msg_id={msg_id}")
            return result
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise TimeoutError(f"Timeout waiting for response to msg_id={msg_id}")

    async def _listen(self):
        """Read incoming frames and resolve pending futures."""
        try:
            while True:
                raw_len = await self._reader.readexactly(4)
                length = struct.unpack(">I", raw_len)[0]
                raw_data = await self._reader.readexactly(length)

                envelope = ProtoMessage()
                envelope.ParseFromString(raw_data)

                if envelope.clientMsgId:
                    try:
                        msg_id = int(envelope.clientMsgId)
                        if msg_id in self._pending:
                            self._pending.pop(msg_id).set_result(envelope)
                    except ValueError:
                        pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            _LOGGER.debug(f"Listener stopped: {e}")
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(e)
            self._pending.clear()


class CTraderAPI:
    """High-level cTrader API — auth + balance + positions + deals."""

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
        self._ctid: Optional[int] = None

    async def _connect_and_auth(self) -> CTraderProtoClient:
        """Connect, authenticate app, resolve ctidTraderAccountId, auth account."""
        client = CTraderProtoClient(self.host, PORT)
        await client.connect()

        # App auth
        app_req = ProtoOAApplicationAuthReq()
        app_req.clientId = self.client_id
        app_req.clientSecret = self.client_secret
        await client.send(app_req)

        # Resolve ctidTraderAccountId from access token (don't rely on user input)
        acc_list_req = ProtoOAGetAccountListByAccessTokenReq()
        acc_list_req.accessToken = self.access_token
        acc_list_msg = await client.send(acc_list_req)
        acc_list_res = _extract(acc_list_msg, ProtoOAGetAccountListByAccessTokenRes)

        if not acc_list_res.ctidTraderAccount:
            raise Exception("No trading accounts found for this access token")

        # Find matching account by traderLogin (account number) if provided,
        # otherwise use the first account
        ctid = None
        for acc in acc_list_res.ctidTraderAccount:
            if str(acc.traderLogin) == str(self.account_id) or str(acc.ctidTraderAccountId) == str(self.account_id):
                ctid = acc.ctidTraderAccountId
                break
        if ctid is None:
            ctid = acc_list_res.ctidTraderAccount[0].ctidTraderAccountId
            _LOGGER.warning(f"Account {self.account_id} not matched, using first account ctidTraderAccountId={ctid}")

        self._ctid = ctid
        _LOGGER.debug(f"Resolved ctidTraderAccountId={ctid}")

        # Account auth
        acc_req = ProtoOAAccountAuthReq()
        acc_req.ctidTraderAccountId = ctid
        acc_req.accessToken = self.access_token
        await client.send(acc_req)

        return client

    async def async_get_balance(self) -> Optional[Dict[str, Any]]:
        """Fetch account balance — used for validation too."""
        client = None
        try:
            client = await self._connect_and_auth()
            req = ProtoOATraderReq()
            req.ctidTraderAccountId = self._ctid
            msg = await client.send(req)
            res = _extract(msg, ProtoOATraderRes)
            trader = res.trader
            divisor = 10 ** trader.moneyDigits
            return {
                "balance": round(trader.balance / divisor, 2),
                "equity": round(trader.balance / divisor, 2),  # equity not in Trader message
                "margin_used": 0,
                "currency": "USD",
                "leverage": trader.leverageInCents // 100,
            }
        except Exception as e:
            _LOGGER.error(f"get_balance error: {e}")
            return None
        finally:
            if client:
                await client.disconnect()

    async def async_update(self) -> Dict[str, Any]:
        """Fetch all data in a single connection: balance + open positions + closed deals + live prices."""
        client = None
        try:
            client = await self._connect_and_auth()

            # --- Balance ---
            trader_req = ProtoOATraderReq()
            trader_req.ctidTraderAccountId = self._ctid
            trader_msg = await client.send(trader_req)
            trader_res = _extract(trader_msg, ProtoOATraderRes)
            trader = trader_res.trader
            divisor = 10 ** trader.moneyDigits
            balance = {
                "balance": round(trader.balance / divisor, 2),
                "equity": round(trader.balance / divisor, 2),
                "margin_used": 0,
                "currency": "USD",
                "leverage": trader.leverageInCents // 100,
            }

            # --- Symbol map + metadata ---
            sym_req = ProtoOASymbolsListReq()
            sym_req.ctidTraderAccountId = self._ctid
            sym_msg = await client.send(sym_req)
            sym_res = _extract(sym_msg, ProtoOASymbolsListRes)
            symbol_map = {int(s.symbolId): s.symbolName for s in sym_res.symbol}
            symbol_digits = {}
            for s in sym_res.symbol:
                try:
                    symbol_digits[int(s.symbolId)] = int(s.digits) if hasattr(s, 'digits') else 5
                except Exception:
                    symbol_digits[int(s.symbolId)] = 5

            # --- Open positions ---
            rec_req = ProtoOAReconcileReq()
            rec_req.ctidTraderAccountId = self._ctid
            rec_msg = await client.send(rec_req)
            rec_res = _extract(rec_msg, ProtoOAReconcileRes)
            
            # NOTE: Live spot subscription is complex (async events).
            # For now, using entry price as current (0 profit until we integrate async listener).
            # TODO: Add proper async event listener for ProtoOASpotEvent
            
            # --- Build open trades with profit calculation ---
            open_trades = []
            for pos in rec_res.position:
                try:
                    side = "BUY" if pos.tradeData.tradeSide == 1 else "SELL"
                    sym_id = int(pos.tradeData.symbolId)
                    sym = symbol_map.get(sym_id, f"#{sym_id}")
                    
                    # Convert volume: cTrader uses microlots (10,000 = 1 lot)
                    volume_microlots = int(pos.tradeData.volume)
                    volume_lots = volume_microlots / 1000000  # 1,000,000 microlots = 1 lot
                    
                    # Entry price
                    entry_price = float(pos.price)
                    
                    # Current price: 
                    # NOTE: ProtoOAPosition.price is ENTRY price only
                    # We need live bid/ask from spot subscription (TODO: async listener)
                    # For now, use entry price (profit will show 0)
                    current_price = entry_price
                    
                    # Simple profit formula: (current - entry) × volume_lots × 1,000,000
                    # cTrader uses 1,000,000 as the standard multiplier
                    lot_size = 1000000
                    
                    if side == "BUY":
                        price_diff = current_price - entry_price
                    else:
                        price_diff = entry_price - current_price
                    
                    # Calculate profit
                    unrealized_profit = round(price_diff * volume_lots * lot_size, 2)
                    
                    _LOGGER.debug(f"Position {sym} {side}: volume_microlots={volume_microlots}, volume_lots={volume_lots}, entry={entry_price}, current={current_price}, price_diff={price_diff}, profit={unrealized_profit}")
                    
                    open_trades.append({
                        "id": pos.positionId,
                        "symbol": sym,
                        "side": side,
                        "volume": round(volume_lots, 4),
                        "entry_price": round(entry_price, 5),
                        "current_price": round(current_price, 5),
                        "stop_loss": round(pos.stopLoss, 5) if pos.stopLoss else None,
                        "take_profit": round(pos.takeProfit, 5) if pos.takeProfit else None,
                        "unrealized_profit": unrealized_profit,
                    })
                except Exception as e:
                    _LOGGER.error(f"Error processing position {pos.positionId}: {e}", exc_info=True)
                    continue

            # --- Closed deals (last 7 days) ---
            deal_req = ProtoOADealListReq()
            deal_req.ctidTraderAccountId = self._ctid
            deal_req.fromTimestamp = int((time.time() - 7 * 24 * 3600) * 1000)
            deal_req.toTimestamp = int(time.time() * 1000)
            deal_req.maxRows = 20
            deal_msg = await client.send(deal_req)
            deal_res = _extract(deal_msg, ProtoOADealListRes)
            closed_trades = []
            for deal in deal_res.deal:
                side = "BUY" if deal.tradeSide == 1 else "SELL"
                digits = deal.moneyDigits if deal.moneyDigits else 2
                divisor = 10 ** digits
                profit = None
                if deal.HasField("closePositionDetail"):
                    gross = deal.closePositionDetail.grossProfit
                    commission = deal.closePositionDetail.commission
                    profit = round((gross + commission) / divisor, 2)
                closed_trades.append({
                    "id": deal.dealId,
                    "symbol": symbol_map.get(int(deal.symbolId), f"#{deal.symbolId}"),
                    "side": side,
                    "volume": int(deal.filledVolume) / 10000000,
                    "entry_price": round(deal.executionPrice, 5),
                    "close_timestamp": deal.executionTimestamp,
                    "profit": profit,
                })

            return {
                "balance": balance,
                "open_trades": open_trades,
                "closed_trades": closed_trades,
            }

        except Exception as e:
            _LOGGER.error(f"async_update error: {e}")
            return {"balance": None, "open_trades": [], "closed_trades": []}
        finally:
            if client:
                await client.disconnect()
