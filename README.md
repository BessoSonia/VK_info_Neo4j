# VK_info

## Описание

Приложение для записи информации о пользователях ВКонтакте в БД Neo4j.


## Установка

1. **Склонируйте репозиторий:**
   ```bash
   cd директория_для_клонирования
   git clone https://github.com/BessoSonia/VK_info_Neo4j


2. **Создайте переменные окружения**
   Запустите командную строку от имени администратора

   ```bash
   set VK_ACCESS_TOKEN=ваш_токен_доступа
   set NEO4J_URI=ваша_конфигурация_neo4j
   set NEO4J_USER=ваша_конфигурация_neo4j
   set NEO4J_PASSWORD=ваша_конфигурация_neo4j
   ```


3. **Установите зависимости**

   ```
    pip install -r requirements.txt
   ```


3. **Запустите приложения**

   ```bash
   python VK_info_Neo4j/vk_neo4j.py
   ```


4. **Введите параметры**

   Введите иденификатор пользователя (необязательно)