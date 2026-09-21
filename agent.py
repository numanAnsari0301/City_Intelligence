from dotenv import load_dotenv

load_dotenv()

import os
from datetime import datetime, timedelta, timezone

import requests
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from tavily import TavilyClient


DEFAULT_MODEL = "gemini-3.6-flash"


SYSTEM_PROMPT = """You are Mr. Mausam Khabri.

You ONLY answer questions about:
- weather
- local news

Use get_weather for weather questions.
Use get_news for news questions.
Use both tools when the user asks for both.

Do not use unnecessary tools.
Do not guess information.

For unrelated questions, reply exactly:
"Sorry, I can only help with weather and local news-related questions."
"""


@tool
def get_weather(city: str) -> str:
    """Get current weather of a city."""

    api_key = os.getenv("OPENWEATHER_API_KEY")

    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={api_key}&units=metric"
    )

    try:
        response = requests.get(url, timeout=5)
        data = response.json()

    except requests.RequestException as e:
        return f"Error : Could not reach weather service ({e})"

    if str(data.get("cod")) != "200":
        return f"Error : {data.get('message', 'Could not fetch weather')}"

    temp = data["main"]["temp"]
    desc = data["weather"][0]["description"]

    return f"Weather in {city}: {desc}, {temp}°C"


tavily_client = TavilyClient(
    api_key=os.getenv("TAVILY_API_KEY")
)


@tool
def get_news(city: str) -> str:
    """Get the latest news of a city."""

    query = f"latest news in {city}"

    try:
        response = tavily_client.search(
            query=query,
            search_depth="basic",
            max_results=3,
        )

    except Exception as e:
        return f"Error : Could not fetch news ({e})"

    results = response.get("results", [])

    if not results:
        return f"No recent news found for {city}"

    formatted = f"Latest News for {city}:\n\n"

    for i, article in enumerate(results, 1):
        formatted += f"{i}. {article['title']}\n"
        formatted += f"{article['url']}\n\n"

    return formatted


def compass(deg) -> str:
    """Convert wind direction degrees to compass direction."""

    if deg is None:
        return ""

    points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

    return points[int((deg + 22.5) % 360 // 45)]


def get_weather_details(city: str) -> dict:
    """
    Full weather report for the UI.

    Uses OpenWeather for current conditions and Open-Meteo
    for UV index.

    Returns {"error": "..."} if something fails.
    """

    api_key = os.getenv("OPENWEATHER_API_KEY")

    if not api_key:
        return {"error": "OPENWEATHER_API_KEY is missing."}

    try:
        response = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "q": city,
                "appid": api_key,
                "units": "metric",
            },
            timeout=5,
        )

        data = response.json()

    except requests.RequestException as e:
        return {"error": f"Could not reach weather service: {e}"}

    if str(data.get("cod")) != "200":
        return {
            "error": data.get(
                "message",
                "Could not fetch weather.",
            )
        }

    try:
        lat = data["coord"]["lat"]
        lon = data["coord"]["lon"]

        uv_response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "uv_index",
            },
            timeout=5,
        )

        uv_data = uv_response.json()

        uv_index = (
            uv_data
            .get("current", {})
            .get("uv_index")
        )

    except requests.RequestException:
        uv_index = None

    main = data.get("main", {})
    weather = data.get("weather", [{}])[0]
    wind = data.get("wind", {})

    timezone_offset = data.get("timezone", 0)

    local_time = datetime.now(
        timezone.utc
    ) + timedelta(seconds=timezone_offset)

    return {
        "city": data.get("name", city),
        "country": data.get("sys", {}).get("country"),
        "temperature": main.get("temp"),
        "feels_like": main.get("feels_like"),
        "temp_min": main.get("temp_min"),
        "temp_max": main.get("temp_max"),
        "humidity": main.get("humidity"),
        "pressure": main.get("pressure"),
        "visibility": (
            data.get("visibility", 0) / 1000
            if data.get("visibility") is not None
            else None
        ),
        "description": weather.get("description"),
        "icon": weather.get("icon"),
        "wind_speed": wind.get("speed"),
        "wind_direction": compass(
            wind.get("deg")
        ),
        "clouds": data.get("clouds", {}).get("all"),
        "sunrise": data.get("sys", {}).get("sunrise"),
        "sunset": data.get("sys", {}).get("sunset"),
        "uv_index": uv_index,
        "local_time": local_time,
    }


TOOLS = [
    get_news,
    get_weather,
]


def build_agent(model_name: str = DEFAULT_MODEL):
    """
    Create the LangChain agent.

    The model is created only when the function is called,
    so importing this file does not require an API call.
    """

    model = ChatGoogleGenerativeAI(
        model=model_name
    )

    return create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )


def message_text(content) -> str:
    """Convert LangChain message content into plain text."""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(
                        item.get("text", "")
                    )

        return "".join(parts)

    return str(content)


if __name__ == "__main__":

    agent = build_agent()

    messages = []

    print(
        "City assistant. Type exit to quit.\n"
    )

    while True:

        user_input = input("you: ").strip()

        if user_input.lower() == "exit":
            break

        messages.append(
            {
                "role": "user",
                "content": user_input,
            }
        )

        messages = messages[-6:]

        result = agent.invoke(
            {
                "messages": messages
            }
        )

        messages = [
            {
                "role": (
                    "user"
                    if m.type == "human"
                    else "assistant"
                ),
                "content": message_text(
                    m.content
                ),
            }
            for m in result["messages"]
            if m.type in ("human", "ai")
            and message_text(m.content).strip()
        ]

        print(
            f"\nAI: {messages[-1]['content']}\n"
        )