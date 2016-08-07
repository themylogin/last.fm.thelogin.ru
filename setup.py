from setuptools import find_packages, setup

setup(
    name="last.fm",
    packages=find_packages(exclude=[]),
    install_requires=[
        "alembic==0.8.6",
        "beautifulsoup4==4.5.0",
        "celery==3.1.23",
        "feedparser==5.2.1",
        "Flask==0.11.1",
        "Flask-Bootstrap==3.3.6.0",
        "Flask-Cache==0.13.1",
        "Flask-Login==0.3.2",
        "Flask-Restful==0.3.5",
        "Flask-Script==2.0.5",
        "Flask-Security==1.7.5",
        "Flask-SQLAlchemy==2.1",
        "Flask-Testing==0.5.0",
        "Flask-WTF==0.12",
        "gevent==1.1.2",
        "gevent-websocket==0.9.5",
        "gunicorn==19.6.0",
        "jinja2-pluralize-filter==0.0.2",
        "lxml==3.6.1",
        "numpy==1.11.1",
        "oauth2==1.9.0.post1",
        "Pillow==3.2.0",
        "psycopg2==2.6.1",
        "pylast==1.6.0",
        "PyRSS2Gen",
        "python-twitter==3.1",
        "pytils==0.2.3",
        "raven[flask]==5.18.0",
        "redis==2.10.5",
        "redlock==1.2.0",
        "scipy==0.18.0",
        "sqlalchemy-citext==1.3.post0",
        "texttable==0.8.4",
        "themyutils",
        "twitter-overkill[client]",
        "whatapi==0.1.2",
    ],
    dependency_links=[
        "https://github.com/themylogin/themyutils/zipball/master#egg=themyutils",
        "https://github.com/themylogin/twitter-overkill/zipball/master#egg=twitter-overkill"
    ]
)
