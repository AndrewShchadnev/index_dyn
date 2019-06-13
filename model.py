from sqlalchemy import *

metadata = MetaData()

md5 = Table('md5', metadata,
            Column('MSISDN', BigInteger, nullable=False, primary_key=True),
            Column('MD5', String(32), unique=True)
            )