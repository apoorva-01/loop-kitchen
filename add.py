import pandas as pd
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app import db, StoreStatus

# Create a Flask application
app = Flask(__name__)

# Configure the SQLAlchemy database connection
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/loopkitchen'
db.init_app(app)

# Read the CSV file
df = pd.read_csv('storestatus.csv')

# Create an application context
with app.app_context():
    # Iterate over each row in the DataFrame
    for _, row in df.iterrows():
        # Create a new StoreStatus object and assign values from the CSV row
        store_status = StoreStatus(
            store_id=row['store_id'],
            timestamp_utc=row['timestamp_utc'],
            status=row['status']
        )
        # print(store_status)

        # Add the StoreStatus object to the session
        db.session.add(store_status)

    try:
        # Commit the changes to the database
        db.session.commit()
    except Exception as e:
        # Rollback the transaction in case of any error
        db.session.rollback()
        print(f"An error occurred: {str(e)}")

    # Close the database session
    db.session.close()
