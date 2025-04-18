This is **nostalgickr**, a way to see your flickr photos that sort of resembles the flickr of 2005.

![a screenshot of the web application homepage](https://images.rtijn.org/2025/nostalgickr.png)

How to install and use:

You need docker running. Well, you can technically run directly with `uvicorn` but you'd have to figure out the redis setup.

1. Get a Flickr API key
2. Copy `.env.example` to `.env` and put in your Flickr API key and secret
3. `docker compose up --build`

Your nostalgickr instance is now running on `http://localhost:8080`
