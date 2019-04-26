CREATE TABLE watertemp (
sqltime TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
watertemp VARCHAR(10) NOT NULL
);

CREATE TABLE subscribe_attempts (
  phone_number STRING,
  sqltime TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE text_subscriptions (
  phone_number STRING NOT NULL,
  verification_time TIMESTAMP NOT NULL
);

CREATE TABLE water_ratings (
  update_sqltime TIMESTAMP,
  feedback STRING NOT NULL,
  sqltime TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);
