from flask import Flask, render_template, request
import requests
from datetime import datetime
from config import (
    API_BASE_URL,
    X_OKAPI_TENANT_VALUE,
    USERNAME,
    PASSWORD
)

app = Flask(__name__)

# Authentication
def login_and_get_token(session: requests.Session) -> str:
    """
    Authenticates with the FOLIO system and returns an access token.

    Parameters:
    session (requests.Session): An existing requests session with the required tenant header.

    Returns:a string with the authentication token obtained from Folio cookies.

    """
    login_url = f"{API_BASE_URL}/authn/login-with-expiry"
    payload = {
        "username": USERNAME,
        "password": PASSWORD
    }

    response = session.post(login_url, json=payload)
    response.raise_for_status()

    for cookie in response.cookies:
        if cookie.name == "folioAccessToken":
            return cookie.value

    raise Exception("Authentication failed: access token not found in cookies")


# Create Session
def create_authenticated_session() -> requests.Session:
    """
    Creates a fully authenticated requests.Session for interacting with Folio APIs.

    Returns requests.Session: A session object with tenant header and access token set.

    Uses `login_and_get_token()` internally to retrieve the access token.
    All future API requests made with this session will include the required
    authentication and tenant headers.
    """
    session = requests.Session()

    # Required tenant header for all requests
    session.headers.update({
        "x-okapi-tenant": X_OKAPI_TENANT_VALUE
    })

    token = login_and_get_token(session)

    # Attach token to all future requests
    session.headers.update({
        "x-okapi-token": token
    })

    return session

def search_instances(session, subject, limit=10, offset=0):
    """
       Search Folio instance records by exact subject heading.

       Parameters:
       session: authenticated requests session
       subject: the subject heading to search
       limit: max results per page
       offset: number of results to skip (for pagination)

       Returns:
       dict: API response with matching instances
    """
    url = f"{API_BASE_URL}/search/instances"
    params = {
        "expandAll": "true",
        "query": f'subjects=="{subject}.lower()"',
        "limit": limit,
        "offset": offset
    }

    resp = session.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

# Home page route
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

#Search results page route
@app.route("/results", methods=["GET"])
def results():
    subject = request.args.get("subject", "").strip()
    if not subject:
        return render_template("results.html",
                               records=[],
                               subject="",
                               page=1,
                               total_records=0,
                               limit=10)

    page = int(request.args.get("page", 1))
    limit = 10
    offset = (page - 1) * limit

    try:
        # Get a logged-in session
        session = create_authenticated_session()

        # Search for instances
        data = search_instances(session, subject, limit=limit, offset=offset)
    except Exception as e:
        # Handle errors  for the user
        return render_template("results.html",
                               records=[],
                               subject=subject,
                               page=1,
                               total_records=0,
                               limit=10,
                               error=str(e))

    total_records = data.get("totalRecords", 0)
    instances = data.get("instances", [])

    records = []
    for r in instances:
        # Extract subjects and contributors
        subjects_list = []
        if r.get("subjects"):
            for s in r["subjects"]:
                if isinstance(s, dict) and "value" in s:
                    subjects_list.append(s["value"])
                else:
                    subjects_list.append(str(s))

        # Extract contributors
        contributors_list = []
        if r.get("contributors"):
            for c in r["contributors"]:
                if isinstance(c, dict) and "name" in c:
                    contributors_list.append(c["name"])
                else:
                    contributors_list.append(str(c))

        # Format created date so its more readable
        created_iso = r.get("metadata", {}).get("createdDate", None)
        if created_iso:
                    try:
                        createdDate = datetime.fromisoformat(created_iso.replace("Z", "+00:00")).strftime(
                            "%Y-%m-%d %H:%M")
                    except:
                        createdDate = created_iso
        else:
                    createdDate = "N/A"
        record = {
            "title": r.get("title", "No Title"),
            "subjects": subjects_list,
            "contributors": contributors_list,
            "createdDate": createdDate
        }
        records.append(record)

    return render_template(
        "results.html",
        records=records,
        subject=subject,
        page=page,
        total_records=total_records,
        limit=limit
    )


if __name__ == "__main__":
    app.run(debug=True, port=8000)