# note: unfortunately not yet working

import base64
import traceback
import typing
import asyncio
import os
import io
import json
from av.video.frame import VideoFrame
from PIL import Image
from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from aiohttp import web

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.rtcrtpsender import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError

ROOT = os.path.dirname(__file__)


async def startup_chrome(on_frame: callable, url=None):
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        if url is None:
            try:
                await driver.get('https://buydrm.com/multikey-demo/', wait_load=False)
                play = await driver.find_element(By.XPATH, '//*[@id="player"]/button', timeout=10)
            except:
                traceback.print_exc()
        else:
            await driver.get(url, wait_load=False)

        async def helper(data, *args, **kwargs):
            await on_frame(data, *args, **kwargs)
            await driver.execute_cdp_cmd("Page.screencastFrameAck", {"sessionId": data["sessionId"]})

        await driver.add_cdp_listener("Page.screencastFrame", on_frame)
        await driver.execute_cdp_cmd("Page.startScreencast")

        if url is None:
            try:
                await play.click()
            except:
                traceback.print_exc()
        while True:
            await asyncio.sleep(5)


class RemoteStreamTrack(MediaStreamTrack):
    def __init__(self, kind="video", _id=None) -> None:
        super().__init__()
        self.kind = kind
        if _id is not None:
            self._id = _id
        self.queue: asyncio.Queue = asyncio.Queue()

    async def recv(self):
        """
        Receive the next frame.
        """
        if self.readyState != "live":
            raise MediaStreamError

        frame = await self.queue.get()
        if frame is None:
            self.stop()
            raise MediaStreamError
        return frame


# noinspection PyMethodMayBeStatic
class Server:
    def __init__(self):
        self.on_startup: typing.List[callable] = []
        self.pcs = set()
        self.track = RemoteStreamTrack()
        self.app = web.Application()
        self.app.router.add_get("/", self.index)
        self.app.router.add_get("/client.js", self.javascript)
        self.app.router.add_post("/offer", self.offer)

    async def index(self, request):
        return web.FileResponse(os.path.join(ROOT, "index.html"))

    async def javascript(self, request):
        return web.FileResponse(os.path.join(ROOT, "client.js"))

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        coros = [pc.close() for pc in self.pcs]
        await asyncio.gather(*coros)
        self.pcs.clear()

    async def offer(self, request):
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        pc = RTCPeerConnection()
        self.pcs.add(pc)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print("Connection state is %s" % pc.connectionState)
            if pc.connectionState == "failed":
                await pc.close()
                self.pcs.discard(pc)

        pc.addTrack(self.track)
        await pc.setRemoteDescription(offer)

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
            ),
        )

    def run(self, host="localhost", port=8080):
        self.app.on_startup.extend(self.on_startup)
        web.run_app(self.app, host=host, port=port)


async def on_frame(data: dict, track: RemoteStreamTrack):
    binary = base64.b64decode(data["data"])
    frame = VideoFrame.from_image(Image.open(io.BytesIO(binary)))
    await track.queue.put(frame)


def main():
    server = Server()

    async def startup_helper(a):
        await asyncio.sleep(1)
        asyncio.ensure_future(startup_chrome(lambda d: on_frame(d, server.track)))

    server.on_startup.append(startup_helper)
    server.run()


main()
