import logging
import requests
import os
import time
from neo4j import GraphDatabase

# Конфигурация Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")

# Настройка доступа к VK API
token = os.getenv("VK_ACCESS_TOKEN")
version = 5.131
vk_depth = 2  # Максимальная глубина рекурсии

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

class Neo4jHandler:
    def __init__(self, uri, user, password):
        try:
            logger.info("Подключение к Neo4j успешно установлено.")
        except Exception as e:
            logger.error(f"Ошибка подключения к Neo4j: {e}")
            raise

    def close(self):
        driver.close()

    def create_user(self, user):
        query = """
        MERGE (u:User {id: $id})
        SET u.screen_name = $screen_name,
            u.name = $name,
            u.sex = $sex,
            u.city = $city
        """
        try:
            with driver.session() as session:
                session.run(query, **user)
            logger.info(f"Пользователь {user['id']} успешно создан в базе.")
        except Exception as e:
            logger.error(f"Ошибка при создании пользователя {user['id']}: {e}")

    def create_group(self, group):
        query = """
        MERGE (g:Group {id: $id})
        SET g.name = $name,
            g.screen_name = $screen_name
        """
        try:
            with driver.session() as session:
                session.run(query, **group)
            logger.info(f"Группа {group['id']} успешно создана в базе.")
        except Exception as e:
            logger.error(f"Ошибка при создании группы {group['id']}: {e}")

    def create_relationship(self, from_id, to_id, rel_type):
        query = f"""
        MATCH (a:User {{id: $from_id}})
        MATCH (b:User {{id: $to_id}})
        MERGE (a)-[:{rel_type}]->(b)
        """
        try:
            with driver.session() as session:
                session.run(query, from_id=from_id, to_id=to_id)
            logger.info(f"Отношение {rel_type} между {from_id} и {to_id} успешно создано.")
        except Exception as e:
            logger.error(f"Ошибка при создании отношения {rel_type} между {from_id} и {to_id}: {e}")


# Подключение к Neo4j
neo4j_handler = Neo4jHandler(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)


def get_user_data(user_id):
    params = {
        'access_token': token,
        'v': version,
        'user_id': user_id,
        'fields': 'followers_count,sex,city'
    }
    try:
        response = requests.get("https://api.vk.com/method/users.get", params=params)
        data = response.json()

        if 'response' in data:
            user_info = data['response'][0]
            logger.info(f"Данные о пользователе {user_id} успешно получены.")
            if 'deactivated' in user_info:
                logger.warning(f"Пользователь {user_id} удалён или заблокирован.")
                return None
            elif user_info.get('is_closed', False):
                logger.warning(f"Профиль пользователя {user_id} закрыт.")
                return None
            else:
                return {
                    'id': user_info['id'],
                    'screen_name': user_info.get('screen_name', ''),
                    'name': f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}",
                    'sex': user_info.get('sex', 0),
                    'city': user_info.get('city', {}).get('title', '')
                }
        else:
            logger.error(f"Не удалось получить данные о пользователе {user_id}. Ответ VK API некорректен.")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к VK API для пользователя {user_id}: {e}")
        return None


def get_followers(user_id, depth=0, max_depth=2):
    if depth > max_depth:
        return []

    params = {
        'access_token': token,
        'v': version,
        'user_id': user_id,
        'count': 200
    }
    try:
        response = requests.get("https://api.vk.com/method/users.getFollowers", params=params)
        followers_data = response.json()

        if 'response' not in followers_data:
            logger.warning(f"Нет данных о фолловерах для пользователя {user_id}.")
            return []

        followers = followers_data['response']['items']
        for follower_id in followers:
            follower_data = get_user_data(follower_id)
            if follower_data:
                neo4j_handler.create_user(follower_data)
                neo4j_handler.create_relationship(user_id, follower_id, "FOLLOW")
                get_followers(follower_id, depth=depth + 1, max_depth=max_depth)
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к VK API для фолловеров пользователя {user_id}: {e}")


def get_subscriptions(user_id, depth=0, max_depth=2):
    if depth > max_depth:
        return []

    params = {
        'access_token': token,
        'v': version,
        'user_id': user_id,
        'count': 200
    }
    try:
        response = requests.get("https://api.vk.com/method/users.getSubscriptions", params=params)
        subscriptions_data = response.json()

        if 'response' not in subscriptions_data:
            logger.warning(f"Нет данных о подписках для пользователя {user_id}.")
            return []

        subscriptions = subscriptions_data['response']['groups']['items']
        for group_id in subscriptions:
            group_data = get_group_data(group_id)
            if group_data:
                neo4j_handler.create_group(group_data)
                neo4j_handler.create_relationship(user_id, group_id, "SUBSCRIBE")
                time.sleep(0.1)
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к VK API для подписок пользователя {user_id}: {e}")


def get_group_data(group_id):
    params = {
        'access_token': token,
        'v': version,
        'group_id': group_id
    }
    try:
        response = requests.get("https://api.vk.com/method/groups.getById", params=params)
        group_data = response.json()

        if 'response' in group_data:
            group = group_data['response'][0]
            return {
                'id': group['id'],
                'name': group.get('name', ''),
                'screen_name': group.get('screen_name', '')
            }
        else:
            logger.warning(f"Не удалось получить данные о группе {group_id}.")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к VK API для группы {group_id}: {e}")
        return None


def query_database(query):
    with driver.session() as session:
        result = session.run(query)
        return [record for record in result]


if __name__ == "__main__":
    if token:
        time.sleep(1)
        user_id = input("Введите ID пользователя: ")
        if not user_id:
            user_id = 172531131  # Пример ID
        user_data = get_user_data(user_id)
        if user_data:
            neo4j_handler.create_user(user_data)
            get_followers(user_id, max_depth=vk_depth)
            get_subscriptions(user_id, max_depth=vk_depth)

            # Запросы на выборку данных из БД
            total_users_query = "MATCH (u:User) RETURN count(u) AS total_users"
            total_groups_query = "MATCH (g:Group) RETURN count(g) AS total_groups"

            top_users_query = """
                        MATCH (u:User)<-[:FOLLOW]-(f)
                        RETURN u.id AS user_id, u.name AS name, count(f) AS follower_count
                        ORDER BY follower_count DESC LIMIT 5
                    """

            popular_groups_query = """
                        MATCH (g:Group)<-[:SUBSCRIBE]-(u)
                        RETURN g.id AS group_id, g.name as name, count(u) AS subscriber_count
                        ORDER BY subscriber_count DESC LIMIT 5
                    """

            # endregion
            print('\n')
            print('-' * 80)
            print("Запросы на выборку")
            print("Всего пользователей:", query_database(total_users_query)[0]['total_users'])
            print("Всего групп:", query_database(total_groups_query)[0]['total_groups'])

            print("\nТоп-5 пользователей по количеству подписчиков:")
            for record in query_database(top_users_query):
                print(f"ID: {record['user_id']}, {record['name']}. Количество подписчиков: {record['follower_count']}")

            print("\nТоп-5 самых популярных групп:")
            for record in query_database(popular_groups_query):
                print(f"ID: {record['group_id']}, \"{record['name']}\". Подписчиков: {record['subscriber_count']}")

        else:
            logger.error(f"Не удалось получить данные о пользователе {user_id}.")
    else:
        logger.error("Ошибка: токен доступа не найден. Установите переменную окружения VK_ACCESS_TOKEN.")

    neo4j_handler.close()

