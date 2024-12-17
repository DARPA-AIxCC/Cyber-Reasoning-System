import asyncio
import tornado

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("PING")

def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/health", MainHandler),
    ])

async def main():
    app = make_app()
    app.listen(9044)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())