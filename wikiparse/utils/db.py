from functools import reduce
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import select


def select_or_insert(session, table, insert_kwargs=None, **kwargs):
    # print('select_or_insert', session, table, insert_kwargs, kwargs)
    get_kwargs = kwargs.items()
    assert len(get_kwargs) >= 1
    with session.begin_nested():

        def get_result():
            eq_iter = (getattr(table.c, k) == v for k, v in get_kwargs)
            my_all = reduce(lambda x, y: x & y, eq_iter)
            return session.execute(select([table]).where(my_all)).fetchone()

        result = get_result()
        if result is not None:
            return result, False
        kwargs.update(insert_kwargs or {})
        # print('kwargs', kwargs)
        insert = table.insert().values(**kwargs).returning(table)
        try:
            result = session.execute(insert)
            return result.fetchone(), True
        except IntegrityError as e:
            print("integerr", repr(e.orig.pgcode))
            if e.orig.pgcode != "23505":  # unique_violation
                print(repr(e.orig.pgcode))
                raise
            session.rollback()
            result = get_result()
            if result:
                return result, True
            print("no result", repr(result))
            raise


def insert(session, table, **kwargs):
    return session.execute(table.insert().values(**kwargs))


def insert_get_id(session, table, **kwargs):
    return session.execute(table.insert().values(**kwargs)).inserted_primary_key[0]


def get_session(db):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import scoped_session, sessionmaker

    engine = create_engine(db)
    session = sessionmaker(bind=engine)
    return scoped_session(session)
