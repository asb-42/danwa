
from .database import DMSDB


class ProjectManager:
    def __init__(self, db: DMSDB):
        self.db = db

    def create_project(self, name: str, description: str = "") -> dict:
        return self.db.create_project(name, description)

    def get_project(self, project_id: str) -> dict | None:
        return self.db.get_project(project_id)

    def list_projects(self) -> list[dict]:
        return self.db.list_projects()

    def update_project(
        self,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> dict | None:
        existing = self.db.get_project(project_id)
        if existing is None:
            return None
        updates = {}
        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description
        if not updates:
            return existing
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [project_id]
        self.db.conn.execute(
            f"UPDATE projects SET {set_clause} WHERE id = ?", values
        )
        self.db.conn.commit()
        return self.db.get_project(project_id)

    def delete_project(self, project_id: str) -> bool:
        return self.db.delete_project(project_id)
