-- Runs once on first container start: creates the database used by pytest.
CREATE DATABASE community_connect_test;
\c community_connect_test
CREATE EXTENSION IF NOT EXISTS postgis;
