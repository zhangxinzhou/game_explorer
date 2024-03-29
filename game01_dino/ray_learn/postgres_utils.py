import psycopg2
import uuid
import config_util

# 连接数据库需要提供相应的数据库名称、用户名、密码、地址、端口等信息

config = config_util.get_config()
db = config['postgres']['db']
host = config['postgres']['host']
port = config['postgres']['port']
user = config['postgres']['user']
pw = config['postgres']['pw']

conn = psycopg2.connect(database=db, host=host, port=port, user=user, password=pw)
curs = conn.cursor()


def generate_uuid():
    return uuid.uuid4().hex


def conn_close():
    curs.close()
    conn.close()


def get_insert_sql(table_name, row: dict):
    sql = f'insert into {table_name}'
    key_str = ""
    val_str = ""
    for index, (key, value) in enumerate(row.items()):
        if value is None:
            continue
        prefix = "" if index == 0 else ","
        if isinstance(value, str):
            value = "'" + value + "'"
        key_str += prefix + key
        val_str += prefix + str(value)
    sql += " (" + key_str + ") values (" + val_str + ");"
    return sql


def insert_model_generation(data):
    if isinstance(data, dict):
        row = data
        sql = get_insert_sql(table_name="model_era", row=row)
        curs.execute(sql)
    elif isinstance(data, list):
        for row in data:
            sql = get_insert_sql(table_name="model_era", row=row)
            curs.execute(sql)
    # 提交事务
    curs.execute("commit;")


def insert_model_train_detail(data):
    if isinstance(data, dict):
        row = data
        sql = get_insert_sql(table_name="model_train_detail", row=row)
        curs.execute(sql)
    elif isinstance(data, list):
        for row in data:
            sql = get_insert_sql(table_name="model_train_detail", row=row)
            curs.execute(sql)
    # 提交事务
    curs.execute("commit;")


def fetchone_to_dict(row, description: tuple) -> dict:
    if row is None or len(row) == 0:
        return None
    else:
        obj = {}
        for index, column in enumerate(description):
            column_name = column[0]
            obj[column_name] = row[index]
        return obj


def fetchall_to_list(rows, description: tuple) -> list:
    if rows is None or len(rows) == 0:
        return []
    else:
        obj_list = []
        for row in rows:
            obj = {}
            for index, column in enumerate(description):
                column_name = column[0]
                obj[column_name] = row[index]
            obj_list.append(obj)
        return obj_list


def query_one_by_sql(sql: str) -> dict:
    curs.execute(sql)
    row = curs.fetchone()
    description = curs.description
    return fetchone_to_dict(row, description)


def query_list_by_sql(sql: str) -> list:
    curs.execute(sql)
    rows = curs.fetchall()
    description = curs.description
    return fetchall_to_list(rows, description)


def query_one_training_model_generation():
    # 优先获取训练中的模型-模型未训练完,找一个
    training_status = 'training'
    sql = f"select * from model_generation where training_status = '{training_status}' order by generation_num asc"
    curs.execute(sql)
    row = curs.fetchone()
    if row is not None:
        description = curs.description
        return fetchone_to_dict(row, description)

    # 如果找不到待训练(training)的模型,则从待开始训练的模型中,找一个
    training_status = 'init'
    sql = f"select * from model_generation where training_status = '{training_status}' order by generation_num asc"
    curs.execute(sql)
    row = curs.fetchone()
    if row is not None:
        description = curs.description
        return fetchone_to_dict(row, description)

    # 既没有训练中的模型,也没有待开始的模型
    return None


def count_model_generation() -> int:
    sql = "select count(*) total from model_era"
    obj = query_one_by_sql(sql)
    return obj.get("total", 0)


def query_max_generation_num() -> int:
    sql = "select max(generation_num) num from model_generation"
    obj = query_one_by_sql(sql)
    return obj.get("num", 0)


def query_max_age_by_model_id(model_id: str) -> int:
    sql = f"select coalesce(max(age_num),0) age_max from model_train_detail where model_id = '{model_id}'"
    obj = query_one_by_sql(sql)
    return obj.get("age_max", 0)


def count_model_generation_by_generation_num(generation_num: int) -> int:
    sql = f"select count(*) total from model_generation where generation_num = {generation_num}"
    obj = query_one_by_sql(sql)
    return obj.get("total", 0)


def query_one_model_generation_by_model_id(model_id):
    sql = f"select * from model_generation where model_id = '{model_id}'"
    return query_one_by_sql(sql)


def query_list_model_generation_by_generation_num(generation_num: int) -> list:
    sql = f"select * from model_generation where generation_num = {generation_num}"
    return query_list_by_sql(sql)


def query_list_model_train_detail_by_model_id(model_id):
    sql = f"select * from model_train_detail where model_id = '{model_id}'"
    return query_list_by_sql(sql)


def update_model_generation_start_time(model_id: str):
    sql = f'''
        update model_generation 
        set 
        training_status = 'training',
        training_start_date = now(),
        updated_date = now()
        where model_id = '{model_id}'
    '''
    curs.execute(sql)
    curs.execute("commit;")


def update_model_generation_end_time(model_id: str, model_path: str, best_age, best_score, train_info):
    sql = f'''
        update model_generation 
        set 
        training_status = 'finished',
        training_end_date  = now(),
        training_cost_time = now() - training_start_date,
        model_path = '{model_path}',
        best_age = {best_age},
        best_score = {best_score},
        train_info = '{train_info}',
        updated_date = now()
        where model_id = '{model_id}'
    '''
    curs.execute(sql)
    curs.execute("commit;")


def update_model_train_detail_start_time(train_id: str):
    sql = f'''
        update model_train_detail 
        set 
        training_start_date = now(),
        updated_date = now()
        where train_id  = '{train_id}'
    '''
    curs.execute(sql)
    curs.execute("commit;")


def update_model_train_detail_end_time(train_id: str, score_total):
    sql = f'''
        update model_train_detail 
        set 
        updated_date = now(),
        training_end_date  = now(),
        training_cost_time = now() - training_start_date,
        score_total = {score_total}
        where train_id  = '{train_id}'
    '''
    curs.execute(sql)
    curs.execute("commit;")


def delete_all_data():
    curs.execute("delete from model_generation;")
    curs.execute("delete from model_train_detail;")
    curs.execute("commit;")


if __name__ == '__main__':
    # 数据测试
    # model_id = generate_uuid()
    # model_obj = {
    #     "model_id": model_id,
    # }
    # train_list = [
    #     {"model_id": model_id, "train_id": generate_uuid()},
    #     {"model_id": model_id, "train_id": generate_uuid()},
    #     {"model_id": model_id, "train_id": generate_uuid()}
    # ]
    # insert_model_generation(model_obj)
    # insert_model_train_detail(train_list)
    # oo: dict = query_one_model_generation_by_model_id(model_id)
    # ll: list = query_list_model_train_detail_by_model_id(model_id)
    # print(oo)
    # for item in ll:
    #     print(item)
    count = count_model_generation()
    print(count)
