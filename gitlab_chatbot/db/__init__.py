from __future__ import annotations
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Literal,
)
from sqlalchemy import (
    ColumnExpressionArgument,
    Row,
    select,
    MetaData,
    create_engine,
    NullPool,
    func,
    or_,
    asc,
    desc,
)
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from gitlab_chatbot.settings import config


JoinData = Tuple[Any, Any]

if TYPE_CHECKING:
    from sqlalchemy.sql._typing import _JoinTargetArgument, _OnClauseArgument

    JoinData = Tuple[_JoinTargetArgument, _OnClauseArgument]

V = TypeVar("V", bound=Type)


class CRUDCapability(Generic[V]):
    resource_db: Type[V]

    def __init__(self, resource_db: Type[V]) -> None:
        self.resource_db = resource_db

    def db_row_to_model(self, row: V):
        return {field.name: getattr(row, field.name) for field in row.__table__.c}

    def db_tuple_row_to_model(self, row: Row[Tuple[V]], columns: list[str]) -> dict:
        return {field[0]: field[1] for field in zip(columns, row)}

    def db_rows_to_model_list(self, rows: Sequence[V]) -> list[dict]:
        return [
            {field.name: getattr(r, field.name) for field in r.__table__.c}
            for r in rows
        ]

    def db_tuple_rows_to_model_list(
        self, rows: Sequence[Row[Tuple[V]]], columns: list[str]
    ) -> list[dict]:
        return [{field[0]: field[1] for field in zip(columns, r)} for r in rows]

    def get_session_factory(self, url: str) -> Callable[..., Session]:
        """
        This method gets the secret from the secret store via a cached function
        and returns a session factory.
        """
        session_factory: Callable[..., Session] = self.create_factory(url)
        return session_factory

    def create_factory(self, url: str) -> Callable[..., Session]:
        engine = create_engine(url, poolclass=NullPool)
        session_factory = sessionmaker(engine, expire_on_commit=False)
        meta = MetaData()
        meta.bind = engine  # type: ignore

        session_db: Callable[..., Session] = scoped_session(
            session_factory=session_factory
        )
        return session_db

    def get_session(
        self,
        factory: Callable[..., Session],
    ):
        session = factory()
        try:
            yield session

        except Exception as e:
            raise e
        finally:
            session.close()

    def get_sync_session(self) -> Session:
        factory = self.get_session_factory(config.db_url)
        session = next(self.get_session(factory=factory))
        return session

    def list_resource(
        self,
        columns: list[str] | None = None,
        join_data: JoinData | None = None,  # type: ignore
        where: list["ColumnExpressionArgument[bool]"] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        like_query: dict[str, str] | None = None, 
        order_by: list[str] | None = None,
        join_type: Literal["OUTER", "FULL"] | None = None,
    ) -> list[dict[str, Any]]:
        if columns is None:
            if join_data:
                stmt = select(self.resource_db, join_data[0])
            else:
                stmt = select(self.resource_db)
        else:
            if join_data:
                attrs = []
                for column in columns:
                    if "." in column:
                        left, right = column.split(".")
                        if self.resource_db.__name__ == left:
                            attrs.append(getattr(self.resource_db, right))
                        elif join_data[0].__name__ == left:
                            attrs.append(getattr(join_data[0], right))
                        else:
                            continue
                    else:
                        attrs.append(getattr(self.resource_db, column))
                stmt = select(*attrs)
            else:
                stmt = select(
                    *[getattr(self.resource_db, column) for column in columns]
                )
        if join_data is not None:
            outer = False
            full = False
            if join_type is not None:
                if join_type == "OUTER":
                    outer = True
                if join_type == "FULL":
                    full = True
            stmt = stmt.join(*join_data, isouter=outer, full=full)
        if where is not None:
            stmt = stmt.where(*where)
        if like_query is not None:
            or_conditions = []
            for column_name, search_value in like_query.items():
                column = getattr(self.resource_db, column_name)
                or_conditions.append(
                    func.lower(column).like(f"%{search_value.lower()}%")
                )
            stmt = stmt.where(or_(*or_conditions))
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        if order_by is not None:
            order_by_clauses = []
            for item in order_by:
                if item.startswith("-"):
                    column = getattr(self.resource_db, item[1:])
                    order_by_clauses.append(desc(column))
                else:
                    column = getattr(self.resource_db, item)
                    order_by_clauses.append(asc(column))
            stmt = stmt.order_by(*order_by_clauses)

        session = self.get_sync_session()
        if columns is not None:
            resources = session.execute(stmt).all()
            session.close()
            return self.db_tuple_rows_to_model_list(resources, columns)
        else:
            resources = session.scalars(stmt).all()
            session.close()
            return self.db_rows_to_model_list(resources)

    def get_resource(
        self,
        resource_id: int | None,
        columns: list[str] | None = None,
        join_data: JoinData | None = None,  # type: ignore
        where: list["ColumnExpressionArgument[bool]"] | None = None,
    ) -> dict[str, Any] | None:
        if columns is None:
            stmt = select(self.resource_db)
        else:
            stmt = select(*[getattr(self.resource_db, column) for column in columns])
        if resource_id is not None:
            stmt = stmt.where(self.resource_db.id == resource_id)  # type: ignore
        if join_data is not None:
            stmt = stmt.join(*join_data)
        if where is not None:
            stmt = stmt.where(*where)
        session = self.get_sync_session()

        if columns is not None:
            resource = session.execute(stmt).first()
            session.close()
            if resource is None:
                return None
            return self.db_tuple_rows_to_model_list([resource], columns)[0]
        else:
            resource = session.scalars(stmt).first()
            session.close()
            if resource is None:
                return None
            return self.db_row_to_model(resource)

    def create_resource(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        resource = self.resource_db(**data)  # type: ignore
        session = self.get_sync_session()
        session.add(resource)
        session.flush()
        session.commit()
        session.refresh(resource)
        session.close()
        return self.db_row_to_model(resource)  # type: ignore

    def delete_resource(
        self,
        resource_id: int | None = None,
        join_data: JoinData | None = None,  # type: ignore
        where: list["ColumnExpressionArgument[bool]"] | None = None,
    ) -> dict[str, Any] | None:
        if resource_id is None:
            stmt = select(self.resource_db)
        else:
            stmt = select(self.resource_db).where(self.resource_db.id == resource_id)  # type: ignore
        if join_data is not None:
            stmt = stmt.join(*join_data)
        if where is not None:
            stmt = stmt.where(*where)
        session = self.get_sync_session()
        resource = session.scalars(stmt).first()
        if resource is None:
            return None
        session.delete(resource)
        session.flush()
        session.commit()
        session.close()
        return self.db_row_to_model(resource)

    def update_resource(
        self,
        data: dict[str, Any] | None,
        resource_id: int | None = None,
        join_data: JoinData | None = None,  # type: ignore
        where: list["ColumnExpressionArgument[bool]"] | None = None,
    ) -> dict[str, Any] | None:
        if resource_id is None:
            stmt = select(self.resource_db)  # type: ignore
        else:
            stmt = select(self.resource_db).where(self.resource_db.id == resource_id)  # type: ignore
        if join_data is not None:
            stmt = stmt.join(*join_data)
        if where is not None:
            stmt = stmt.where(*where)
        session = self.get_sync_session()
        resource = session.scalars(stmt).first()
        if resource is None:
            return None
        if data is not None:
            for k in data:
                setattr(resource, k, data[k])
        session.add(resource)
        session.flush()
        session.commit()
        session.refresh(resource)
        session.close()
        return self.db_row_to_model(resource)
