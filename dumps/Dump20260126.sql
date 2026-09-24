-- MySQL dump 10.13  Distrib 8.0.44, for Win64 (x86_64)
--
-- Host: localhost    Database: football_league
-- ------------------------------------------------------
-- Server version	8.0.44

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `cards`
--

DROP TABLE IF EXISTS `cards`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cards` (
  `card_id` int NOT NULL AUTO_INCREMENT,
  `match_id` int DEFAULT NULL,
  `player_id` int DEFAULT NULL,
  `card_type` varchar(10) DEFAULT NULL,
  `minute_issued` int DEFAULT NULL,
  `reason` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`card_id`),
  KEY `match_id` (`match_id`),
  KEY `player_id` (`player_id`),
  CONSTRAINT `cards_ibfk_1` FOREIGN KEY (`match_id`) REFERENCES `matches` (`match_id`) ON DELETE CASCADE,
  CONSTRAINT `cards_ibfk_2` FOREIGN KEY (`player_id`) REFERENCES `players` (`player_id`),
  CONSTRAINT `cards_chk_1` CHECK ((`card_type` in (_utf8mb4'Yellow',_utf8mb4'Red')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `cards`
--

LOCK TABLES `cards` WRITE;
/*!40000 ALTER TABLE `cards` DISABLE KEYS */;
/*!40000 ALTER TABLE `cards` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `coaches`
--

DROP TABLE IF EXISTS `coaches`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `coaches` (
  `coach_id` int NOT NULL AUTO_INCREMENT,
  `team_id` int DEFAULT NULL,
  `name` varchar(100) NOT NULL,
  `role` varchar(50) DEFAULT 'Head Coach',
  PRIMARY KEY (`coach_id`),
  KEY `team_id` (`team_id`),
  CONSTRAINT `coaches_ibfk_1` FOREIGN KEY (`team_id`) REFERENCES `teams` (`team_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `coaches`
--

LOCK TABLES `coaches` WRITE;
/*!40000 ALTER TABLE `coaches` DISABLE KEYS */;
INSERT INTO `coaches` VALUES (1,NULL,'Coach Kabir','Head Coach');
/*!40000 ALTER TABLE `coaches` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `goals`
--

DROP TABLE IF EXISTS `goals`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `goals` (
  `goal_id` int NOT NULL AUTO_INCREMENT,
  `match_id` int DEFAULT NULL,
  `player_id` int DEFAULT NULL,
  `minute_scored` int DEFAULT NULL,
  `assist_by_player_id` int DEFAULT NULL,
  PRIMARY KEY (`goal_id`),
  KEY `match_id` (`match_id`),
  KEY `player_id` (`player_id`),
  CONSTRAINT `goals_ibfk_1` FOREIGN KEY (`match_id`) REFERENCES `matches` (`match_id`) ON DELETE CASCADE,
  CONSTRAINT `goals_ibfk_2` FOREIGN KEY (`player_id`) REFERENCES `players` (`player_id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `goals`
--

LOCK TABLES `goals` WRITE;
/*!40000 ALTER TABLE `goals` DISABLE KEYS */;
/*!40000 ALTER TABLE `goals` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `injuries`
--

DROP TABLE IF EXISTS `injuries`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `injuries` (
  `injury_id` int NOT NULL AUTO_INCREMENT,
  `player_id` int DEFAULT NULL,
  `injury_type` varchar(100) DEFAULT NULL,
  `start_date` date DEFAULT NULL,
  `expected_return_date` date DEFAULT NULL,
  `status` varchar(20) DEFAULT 'Active',
  PRIMARY KEY (`injury_id`),
  KEY `player_id` (`player_id`),
  CONSTRAINT `injuries_ibfk_1` FOREIGN KEY (`player_id`) REFERENCES `players` (`player_id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `injuries`
--

LOCK TABLES `injuries` WRITE;
/*!40000 ALTER TABLE `injuries` DISABLE KEYS */;
INSERT INTO `injuries` VALUES (1,2,'Hamstring','2023-10-05',NULL,'Active');
/*!40000 ALTER TABLE `injuries` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Temporary view structure for view `league_standings`
--

DROP TABLE IF EXISTS `league_standings`;
/*!50001 DROP VIEW IF EXISTS `league_standings`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `league_standings` AS SELECT 
 1 AS `team_name`,
 1 AS `played`,
 1 AS `wins`,
 1 AS `draws`,
 1 AS `losses`,
 1 AS `gf`,
 1 AS `ga`,
 1 AS `gd`,
 1 AS `points`*/;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `match_lineups`
--

DROP TABLE IF EXISTS `match_lineups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `match_lineups` (
  `lineup_id` int NOT NULL AUTO_INCREMENT,
  `match_id` int DEFAULT NULL,
  `player_id` int DEFAULT NULL,
  `is_starter` tinyint(1) DEFAULT '1',
  `minutes_played` int DEFAULT '90',
  PRIMARY KEY (`lineup_id`),
  KEY `match_id` (`match_id`),
  KEY `player_id` (`player_id`),
  CONSTRAINT `match_lineups_ibfk_1` FOREIGN KEY (`match_id`) REFERENCES `matches` (`match_id`) ON DELETE CASCADE,
  CONSTRAINT `match_lineups_ibfk_2` FOREIGN KEY (`player_id`) REFERENCES `players` (`player_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `match_lineups`
--

LOCK TABLES `match_lineups` WRITE;
/*!40000 ALTER TABLE `match_lineups` DISABLE KEYS */;
/*!40000 ALTER TABLE `match_lineups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `matches`
--

DROP TABLE IF EXISTS `matches`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `matches` (
  `match_id` int NOT NULL AUTO_INCREMENT,
  `home_team_id` int NOT NULL,
  `away_team_id` int NOT NULL,
  `match_date` datetime NOT NULL,
  `home_score` int DEFAULT NULL,
  `away_score` int DEFAULT NULL,
  `status` varchar(20) DEFAULT 'SCHEDULED',
  PRIMARY KEY (`match_id`),
  KEY `home_team_id` (`home_team_id`),
  KEY `away_team_id` (`away_team_id`),
  CONSTRAINT `matches_ibfk_1` FOREIGN KEY (`home_team_id`) REFERENCES `teams` (`team_id`),
  CONSTRAINT `matches_ibfk_2` FOREIGN KEY (`away_team_id`) REFERENCES `teams` (`team_id`)
) ENGINE=InnoDB AUTO_INCREMENT=470 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `matches`
--

LOCK TABLES `matches` WRITE;
/*!40000 ALTER TABLE `matches` DISABLE KEYS */;
INSERT INTO `matches` VALUES (241,66,80,'2025-08-15 00:00:00',4,2,'SCHEDULED'),(242,62,69,'2025-08-16 00:00:00',0,0,'SCHEDULED'),(243,77,65,'2025-08-16 00:00:00',1,1,'SCHEDULED'),(244,70,79,'2025-08-16 00:00:00',3,0,'SCHEDULED'),(245,71,73,'2025-08-16 00:00:00',3,0,'SCHEDULED'),(246,72,67,'2025-08-16 00:00:00',0,4,'SCHEDULED'),(247,75,78,'2025-08-17 00:00:00',3,1,'SCHEDULED'),(248,63,76,'2025-08-17 00:00:00',0,0,'SCHEDULED'),(249,68,61,'2025-08-17 00:00:00',0,1,'SCHEDULED'),(250,74,64,'2025-08-18 00:00:00',1,0,'SCHEDULED'),(251,79,63,'2025-08-22 00:00:00',1,5,'SCHEDULED'),(252,67,71,'2025-08-23 00:00:00',0,2,'SCHEDULED'),(253,80,72,'2025-08-23 00:00:00',1,0,'SCHEDULED'),(254,78,62,'2025-08-23 00:00:00',1,0,'SCHEDULED'),(255,73,70,'2025-08-23 00:00:00',2,0,'SCHEDULED'),(256,61,74,'2025-08-23 00:00:00',5,0,'SCHEDULED'),(257,76,75,'2025-08-24 00:00:00',1,1,'SCHEDULED'),(258,64,77,'2025-08-24 00:00:00',2,0,'SCHEDULED'),(259,65,68,'2025-08-24 00:00:00',1,1,'SCHEDULED'),(260,69,66,'2025-08-25 00:00:00',2,3,'SCHEDULED'),(261,63,65,'2025-08-30 00:00:00',2,0,'SCHEDULED'),(262,70,78,'2025-08-30 00:00:00',2,1,'SCHEDULED'),(263,68,73,'2025-08-30 00:00:00',3,2,'SCHEDULED'),(264,71,80,'2025-08-30 00:00:00',0,1,'SCHEDULED'),(265,72,64,'2025-08-30 00:00:00',2,3,'SCHEDULED'),(266,74,69,'2025-08-30 00:00:00',0,0,'SCHEDULED'),(267,77,67,'2025-08-31 00:00:00',2,1,'SCHEDULED'),(268,75,79,'2025-08-31 00:00:00',0,3,'SCHEDULED'),(269,66,61,'2025-08-31 00:00:00',1,0,'SCHEDULED'),(270,62,76,'2025-08-31 00:00:00',0,3,'SCHEDULED'),(271,61,75,'2025-09-13 00:00:00',3,0,'SCHEDULED'),(272,80,77,'2025-09-13 00:00:00',2,1,'SCHEDULED'),(273,76,70,'2025-09-13 00:00:00',0,0,'SCHEDULED'),(274,64,62,'2025-09-13 00:00:00',0,0,'SCHEDULED'),(275,65,74,'2025-09-13 00:00:00',1,0,'SCHEDULED'),(276,69,72,'2025-09-13 00:00:00',1,0,'SCHEDULED'),(277,79,71,'2025-09-13 00:00:00',0,3,'SCHEDULED'),(278,78,63,'2025-09-13 00:00:00',2,2,'SCHEDULED'),(279,73,66,'2025-09-14 00:00:00',0,1,'SCHEDULED'),(280,67,68,'2025-09-14 00:00:00',3,0,'SCHEDULED'),(281,66,64,'2025-09-20 00:00:00',2,1,'SCHEDULED'),(282,77,71,'2025-09-20 00:00:00',2,2,'SCHEDULED'),(283,73,75,'2025-09-20 00:00:00',1,1,'SCHEDULED'),(284,79,76,'2025-09-20 00:00:00',1,2,'SCHEDULED'),(285,72,74,'2025-09-20 00:00:00',1,3,'SCHEDULED'),(286,68,63,'2025-09-20 00:00:00',2,1,'SCHEDULED'),(287,65,78,'2025-09-20 00:00:00',3,1,'SCHEDULED'),(288,80,69,'2025-09-21 00:00:00',0,0,'SCHEDULED'),(289,70,62,'2025-09-21 00:00:00',1,1,'SCHEDULED'),(290,61,67,'2025-09-21 00:00:00',1,1,'SCHEDULED'),(291,78,68,'2025-09-27 00:00:00',3,1,'SCHEDULED'),(292,76,66,'2025-09-27 00:00:00',2,1,'SCHEDULED'),(293,63,77,'2025-09-27 00:00:00',1,3,'SCHEDULED'),(294,74,80,'2025-09-27 00:00:00',2,2,'SCHEDULED'),(295,67,73,'2025-09-27 00:00:00',5,1,'SCHEDULED'),(296,75,70,'2025-09-27 00:00:00',0,1,'SCHEDULED'),(297,71,72,'2025-09-27 00:00:00',1,1,'SCHEDULED'),(298,62,65,'2025-09-28 00:00:00',3,1,'SCHEDULED'),(299,69,61,'2025-09-28 00:00:00',1,2,'SCHEDULED'),(300,64,79,'2025-09-29 00:00:00',1,1,'SCHEDULED'),(301,80,65,'2025-10-03 00:00:00',3,1,'SCHEDULED'),(302,74,71,'2025-10-04 00:00:00',1,2,'SCHEDULED'),(303,61,79,'2025-10-04 00:00:00',2,0,'SCHEDULED'),(304,68,70,'2025-10-04 00:00:00',2,0,'SCHEDULED'),(305,63,66,'2025-10-04 00:00:00',2,1,'SCHEDULED'),(306,62,73,'2025-10-05 00:00:00',2,1,'SCHEDULED'),(307,64,76,'2025-10-05 00:00:00',2,1,'SCHEDULED'),(308,69,75,'2025-10-05 00:00:00',2,0,'SCHEDULED'),(309,72,77,'2025-10-05 00:00:00',1,1,'SCHEDULED'),(310,78,67,'2025-10-05 00:00:00',0,1,'SCHEDULED'),(311,75,63,'2025-10-18 00:00:00',0,3,'SCHEDULED'),(312,77,69,'2025-10-18 00:00:00',2,1,'SCHEDULED'),(313,76,80,'2025-10-18 00:00:00',3,3,'SCHEDULED'),(314,73,74,'2025-10-18 00:00:00',2,0,'SCHEDULED'),(315,67,64,'2025-10-18 00:00:00',2,0,'SCHEDULED'),(316,70,72,'2025-10-18 00:00:00',2,0,'SCHEDULED'),(317,65,61,'2025-10-18 00:00:00',0,1,'SCHEDULED'),(318,71,62,'2025-10-19 00:00:00',1,2,'SCHEDULED'),(319,66,68,'2025-10-19 00:00:00',1,2,'SCHEDULED'),(320,79,78,'2025-10-20 00:00:00',0,2,'SCHEDULED'),(321,74,79,'2025-10-24 00:00:00',2,1,'SCHEDULED'),(322,63,70,'2025-10-25 00:00:00',1,2,'SCHEDULED'),(323,69,65,'2025-10-25 00:00:00',2,1,'SCHEDULED'),(324,68,77,'2025-10-25 00:00:00',4,2,'SCHEDULED'),(325,78,66,'2025-10-25 00:00:00',3,2,'SCHEDULED'),(326,80,75,'2025-10-26 00:00:00',2,0,'SCHEDULED'),(327,62,67,'2025-10-26 00:00:00',1,0,'SCHEDULED'),(328,61,76,'2025-10-26 00:00:00',1,0,'SCHEDULED'),(329,72,73,'2025-10-26 00:00:00',2,3,'SCHEDULED'),(330,64,71,'2025-10-26 00:00:00',0,3,'SCHEDULED'),(331,77,74,'2025-11-01 00:00:00',3,0,'SCHEDULED'),(332,76,78,'2025-11-01 00:00:00',2,0,'SCHEDULED'),(333,73,61,'2025-11-01 00:00:00',0,2,'SCHEDULED'),(334,65,72,'2025-11-01 00:00:00',3,0,'SCHEDULED'),(335,75,68,'2025-11-01 00:00:00',2,2,'SCHEDULED'),(336,71,63,'2025-11-01 00:00:00',0,1,'SCHEDULED'),(337,66,62,'2025-11-01 00:00:00',2,0,'SCHEDULED'),(338,79,69,'2025-11-02 00:00:00',3,1,'SCHEDULED'),(339,67,80,'2025-11-02 00:00:00',3,1,'SCHEDULED'),(340,70,64,'2025-11-03 00:00:00',1,1,'SCHEDULED'),(341,71,68,'2025-11-08 00:00:00',2,2,'SCHEDULED'),(342,64,65,'2025-11-08 00:00:00',2,0,'SCHEDULED'),(343,79,73,'2025-11-08 00:00:00',3,2,'SCHEDULED'),(344,70,61,'2025-11-08 00:00:00',2,2,'SCHEDULED'),(345,63,72,'2025-11-08 00:00:00',3,0,'SCHEDULED'),(346,62,80,'2025-11-09 00:00:00',4,0,'SCHEDULED'),(347,76,77,'2025-11-09 00:00:00',0,0,'SCHEDULED'),(348,78,69,'2025-11-09 00:00:00',3,1,'SCHEDULED'),(349,75,74,'2025-11-09 00:00:00',3,1,'SCHEDULED'),(350,67,66,'2025-11-09 00:00:00',3,0,'SCHEDULED'),(351,73,63,'2025-11-22 00:00:00',0,2,'SCHEDULED'),(352,80,79,'2025-11-22 00:00:00',2,2,'SCHEDULED'),(353,77,78,'2025-11-22 00:00:00',2,1,'SCHEDULED'),(354,65,70,'2025-11-22 00:00:00',1,0,'SCHEDULED'),(355,66,75,'2025-11-22 00:00:00',0,3,'SCHEDULED'),(356,72,76,'2025-11-22 00:00:00',0,2,'SCHEDULED'),(357,69,67,'2025-11-22 00:00:00',2,1,'SCHEDULED'),(358,74,62,'2025-11-23 00:00:00',1,2,'SCHEDULED'),(359,61,71,'2025-11-23 00:00:00',4,1,'SCHEDULED'),(360,68,64,'2025-11-24 00:00:00',0,1,'SCHEDULED'),(361,70,80,'2025-11-29 00:00:00',3,2,'SCHEDULED'),(362,78,73,'2025-11-29 00:00:00',3,1,'SCHEDULED'),(363,67,74,'2025-11-29 00:00:00',3,2,'SCHEDULED'),(364,64,69,'2025-11-29 00:00:00',1,4,'SCHEDULED'),(365,71,65,'2025-11-29 00:00:00',1,2,'SCHEDULED'),(366,76,68,'2025-11-30 00:00:00',1,2,'SCHEDULED'),(367,62,72,'2025-11-30 00:00:00',1,0,'SCHEDULED'),(368,75,77,'2025-11-30 00:00:00',0,2,'SCHEDULED'),(369,79,66,'2025-11-30 00:00:00',0,2,'SCHEDULED'),(370,63,61,'2025-11-30 00:00:00',1,1,'SCHEDULED'),(371,80,64,'2025-12-02 00:00:00',0,1,'SCHEDULED'),(372,65,67,'2025-12-02 00:00:00',4,5,'SCHEDULED'),(373,69,71,'2025-12-02 00:00:00',2,2,'SCHEDULED'),(374,77,62,'2025-12-03 00:00:00',3,4,'SCHEDULED'),(375,61,78,'2025-12-03 00:00:00',2,0,'SCHEDULED'),(376,73,76,'2025-12-03 00:00:00',0,1,'SCHEDULED'),(377,72,75,'2025-12-03 00:00:00',0,1,'SCHEDULED'),(378,66,70,'2025-12-03 00:00:00',1,1,'SCHEDULED'),(379,74,63,'2025-12-03 00:00:00',3,1,'SCHEDULED'),(380,68,79,'2025-12-04 00:00:00',1,1,'SCHEDULED'),(381,62,61,'2025-12-06 00:00:00',2,1,'SCHEDULED'),(382,80,63,'2025-12-06 00:00:00',0,0,'SCHEDULED'),(383,64,75,'2025-12-06 00:00:00',3,0,'SCHEDULED'),(384,67,70,'2025-12-06 00:00:00',3,0,'SCHEDULED'),(385,69,73,'2025-12-06 00:00:00',2,1,'SCHEDULED'),(386,71,78,'2025-12-06 00:00:00',2,0,'SCHEDULED'),(387,74,66,'2025-12-06 00:00:00',3,3,'SCHEDULED'),(388,77,79,'2025-12-07 00:00:00',1,1,'SCHEDULED'),(389,65,76,'2025-12-07 00:00:00',1,2,'SCHEDULED'),(390,72,68,'2025-12-08 00:00:00',1,4,'SCHEDULED'),(391,63,64,'2025-12-13 00:00:00',2,0,'SCHEDULED'),(392,66,77,'2025-12-13 00:00:00',2,0,'SCHEDULED'),(393,73,65,'2025-12-13 00:00:00',2,3,'SCHEDULED'),(394,61,72,'2025-12-13 00:00:00',2,1,'SCHEDULED'),(395,70,69,'2025-12-14 00:00:00',1,0,'SCHEDULED'),(396,76,67,'2025-12-14 00:00:00',0,3,'SCHEDULED'),(397,75,71,'2025-12-14 00:00:00',3,0,'SCHEDULED'),(398,79,62,'2025-12-14 00:00:00',2,3,'SCHEDULED'),(399,78,74,'2025-12-14 00:00:00',1,1,'SCHEDULED'),(400,68,80,'2025-12-15 00:00:00',4,4,'SCHEDULED'),(401,69,63,'2025-12-20 00:00:00',2,2,'SCHEDULED'),(402,80,73,'2025-12-20 00:00:00',1,1,'SCHEDULED'),(403,77,70,'2025-12-20 00:00:00',0,0,'SCHEDULED'),(404,67,79,'2025-12-20 00:00:00',3,0,'SCHEDULED'),(405,72,78,'2025-12-20 00:00:00',0,2,'SCHEDULED'),(406,71,66,'2025-12-20 00:00:00',1,2,'SCHEDULED'),(407,64,61,'2025-12-20 00:00:00',0,1,'SCHEDULED'),(408,74,76,'2025-12-20 00:00:00',4,1,'SCHEDULED'),(409,62,68,'2025-12-21 00:00:00',2,1,'SCHEDULED'),(410,65,75,'2025-12-22 00:00:00',1,0,'SCHEDULED'),(411,68,69,'2025-12-26 00:00:00',1,0,'SCHEDULED'),(412,75,67,'2025-12-27 00:00:00',1,2,'SCHEDULED'),(413,61,77,'2025-12-27 00:00:00',2,1,'SCHEDULED'),(414,78,80,'2025-12-27 00:00:00',4,1,'SCHEDULED'),(415,73,64,'2025-12-27 00:00:00',0,0,'SCHEDULED'),(416,66,72,'2025-12-27 00:00:00',2,1,'SCHEDULED'),(417,79,65,'2025-12-27 00:00:00',0,1,'SCHEDULED'),(418,63,62,'2025-12-27 00:00:00',1,2,'SCHEDULED'),(419,70,74,'2025-12-28 00:00:00',1,1,'SCHEDULED'),(420,76,71,'2025-12-28 00:00:00',0,1,'SCHEDULED'),(421,73,69,'2025-12-30 00:00:00',1,3,'SCHEDULED'),(422,63,80,'2025-12-30 00:00:00',2,2,'SCHEDULED'),(423,75,64,'2025-12-30 00:00:00',0,2,'SCHEDULED'),(424,79,77,'2025-12-30 00:00:00',2,2,'SCHEDULED'),(425,61,62,'2025-12-30 00:00:00',4,1,'SCHEDULED'),(426,68,72,'2025-12-30 00:00:00',1,1,'SCHEDULED'),(427,76,65,'2026-01-01 00:00:00',1,1,'SCHEDULED'),(428,66,74,'2026-01-01 00:00:00',0,0,'SCHEDULED'),(429,70,67,'2026-01-01 00:00:00',0,0,'SCHEDULED'),(430,78,71,'2026-01-01 00:00:00',0,0,'SCHEDULED'),(431,62,75,'2026-01-03 00:00:00',3,1,'SCHEDULED'),(432,77,73,'2026-01-03 00:00:00',2,0,'SCHEDULED'),(433,72,79,'2026-01-03 00:00:00',3,0,'SCHEDULED'),(434,80,61,'2026-01-03 00:00:00',2,3,'SCHEDULED'),(435,74,68,'2026-01-04 00:00:00',1,1,'SCHEDULED'),(436,64,78,'2026-01-04 00:00:00',2,4,'SCHEDULED'),(437,69,76,'2026-01-04 00:00:00',2,0,'SCHEDULED'),(438,71,70,'2026-01-04 00:00:00',1,1,'SCHEDULED'),(439,65,66,'2026-01-04 00:00:00',2,2,'SCHEDULED'),(440,67,63,'2026-01-04 00:00:00',1,1,'SCHEDULED'),(441,79,75,'2026-01-06 00:00:00',1,2,'SCHEDULED'),(442,80,71,'2026-01-07 00:00:00',3,2,'SCHEDULED'),(443,76,62,'2026-01-07 00:00:00',0,0,'SCHEDULED'),(444,78,70,'2026-01-07 00:00:00',3,0,'SCHEDULED'),(445,64,72,'2026-01-07 00:00:00',1,1,'SCHEDULED'),(446,65,63,'2026-01-07 00:00:00',2,1,'SCHEDULED'),(447,67,77,'2026-01-07 00:00:00',1,1,'SCHEDULED'),(448,73,68,'2026-01-07 00:00:00',2,2,'SCHEDULED'),(449,69,74,'2026-01-07 00:00:00',4,3,'SCHEDULED'),(450,61,66,'2026-01-08 00:00:00',0,0,'SCHEDULED'),(451,68,67,'2026-01-17 00:00:00',2,0,'SCHEDULED'),(452,70,76,'2026-01-17 00:00:00',2,1,'SCHEDULED'),(453,63,78,'2026-01-17 00:00:00',2,0,'SCHEDULED'),(454,66,73,'2026-01-17 00:00:00',1,1,'SCHEDULED'),(455,74,65,'2026-01-17 00:00:00',1,0,'SCHEDULED'),(456,71,79,'2026-01-17 00:00:00',1,2,'SCHEDULED'),(457,75,61,'2026-01-17 00:00:00',0,0,'SCHEDULED'),(458,72,69,'2026-01-18 00:00:00',0,0,'SCHEDULED'),(459,62,64,'2026-01-18 00:00:00',0,1,'SCHEDULED'),(460,77,80,'2026-01-19 00:00:00',1,1,'SCHEDULED'),(461,79,70,'2026-01-24 00:00:00',3,1,'SCHEDULED'),(462,73,71,'2026-01-24 00:00:00',2,2,'SCHEDULED'),(463,65,77,'2026-01-24 00:00:00',2,1,'SCHEDULED'),(464,67,72,'2026-01-24 00:00:00',2,0,'SCHEDULED'),(465,80,66,'2026-01-24 00:00:00',3,2,'SCHEDULED'),(466,76,63,'2026-01-25 00:00:00',1,3,'SCHEDULED'),(467,78,75,'2026-01-25 00:00:00',0,2,'SCHEDULED'),(468,69,62,'2026-01-25 00:00:00',0,2,'SCHEDULED'),(469,61,68,'2026-01-25 00:00:00',2,3,'SCHEDULED');
/*!40000 ALTER TABLE `matches` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Final view structure for view `league_standings`
--

/*!50001 DROP VIEW IF EXISTS `league_standings`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_0900_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `league_standings` AS select `t`.`name` AS `team_name`,count(`m`.`match_id`) AS `played`,coalesce(sum((case when (((`m`.`home_team_id` = `t`.`team_id`) and (`m`.`home_score` > `m`.`away_score`)) or ((`m`.`away_team_id` = `t`.`team_id`) and (`m`.`away_score` > `m`.`home_score`))) then 1 else 0 end)),0) AS `wins`,coalesce(sum((case when (`m`.`home_score` = `m`.`away_score`) then 1 else 0 end)),0) AS `draws`,coalesce(sum((case when (((`m`.`home_team_id` = `t`.`team_id`) and (`m`.`home_score` < `m`.`away_score`)) or ((`m`.`away_team_id` = `t`.`team_id`) and (`m`.`away_score` < `m`.`home_score`))) then 1 else 0 end)),0) AS `losses`,coalesce(sum((case when (`m`.`home_team_id` = `t`.`team_id`) then `m`.`home_score` else `m`.`away_score` end)),0) AS `gf`,coalesce(sum((case when (`m`.`home_team_id` = `t`.`team_id`) then `m`.`away_score` else `m`.`home_score` end)),0) AS `ga`,coalesce(sum((case when (`m`.`home_team_id` = `t`.`team_id`) then (`m`.`home_score` - `m`.`away_score`) else (`m`.`away_score` - `m`.`home_score`) end)),0) AS `gd`,coalesce(sum((case when (((`m`.`home_team_id` = `t`.`team_id`) and (`m`.`home_score` > `m`.`away_score`)) or ((`m`.`away_team_id` = `t`.`team_id`) and (`m`.`away_score` > `m`.`home_score`))) then 3 when (`m`.`home_score` = `m`.`away_score`) then 1 else 0 end)),0) AS `points` from (`teams` `t` left join `matches` `m` on((((`t`.`team_id` = `m`.`home_team_id`) or (`t`.`team_id` = `m`.`away_team_id`)) and (`m`.`status` = 'FINISHED')))) group by `t`.`team_id` order by `points` desc,`gd` desc,`team_name` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-01-26 18:04:18
