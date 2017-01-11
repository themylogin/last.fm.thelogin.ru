from setuptools import find_packages, setup

setup(
    name="last.fm",
    packages=find_packages(exclude=[]),
    install_requires=[
        "alembic",
        "beautifulsoup4",
        "celery<4",
        "feedparser",
        "Flask",
        "Flask-Bootstrap",
        "Flask-Cache",
        "Flask-Login",
        "Flask-Restful",
        "Flask-Script",
        "Flask-Security",
        "Flask-SQLAlchemy",
        "Flask-Testing",
        "Flask-WTF",
        "gevent",
        "gevent-websocket",
        "gunicorn",
        "ipaddress",
        "jinja2-pluralize-filter",
        "lxml",
        "numpy",
        "oauth2",
        "Pillow",
        "psycopg2",
        "pylast",
        "PyRSS2Gen",
        "python-twitter",
        "pytils",
        "raven[flask]",
        "redis",
        "redlock",
        "scipy",
        "sqlalchemy-citext",
        "texttable",
        "themyutils",
        "twitter-overkill[client]",
        "whatapi",
    ],
    dependency_links=[
        "https://github.com/themylogin/themyutils/zipball/master#egg=themyutils",
        "https://github.com/themylogin/twitter-overkill/zipball/master#egg=twitter-overkill",
    ]
)
