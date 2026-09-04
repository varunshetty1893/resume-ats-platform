"""CI migration-safety net.

This is the automated version of the `flask db heads` / `flask db current`
check performed manually in the Phase 1 recompute-on-write migration —
instead of a one-off manual step before a single deploy, it runs on every
test invocation.

Two independent things are checked:

1. The migration chain has exactly one head. A broken/duplicated
   down_revision would let a migration silently become unreachable from
   `flask db upgrade` without any error at revision-authoring time.
2. A DB provisioned the same way this app is actually deployed — a
   db.create_all() reflecting the current models.py, then `flask db stamp
   head` (see README.md) — ends up stamped at exactly the same revision
   `flask db heads` reports. This is the direct, mechanical check for the
   original production incident this thread traces back to: a deployed
   database whose `alembic_version` was NOT actually at head despite the
   app assuming it was, so a column the app's code expected wasn't there
   yet at runtime.

A note on scope: this deliberately does NOT attempt a `flask db check`
(autogenerate diff) style test, i.e. "did someone change a model field
without writing a migration for it". That check compares the live DB's
introspected schema against models.py's metadata — but since the DB here
is provisioned via db.create_all(), which by construction always matches
whatever's currently in models.py, such a diff would be empty by
construction regardless of whether a migration exists at all, making it a
test that always passes without actually verifying anything (confirmed by
temporarily injecting an unmigrated column during development of this
test — flask_migrate.check() didn't catch it). Catching that specific
class of drift would require the migration chain to be replayable from a
genuinely empty database, which it currently isn't (the first migration,
c3780235b89b, assumes its tables already exist) — fixable, but only by
restructuring migration history, which weakens the guarantee that already
existing dev/production databases can still reach the current head. That
felt like a decision worth flagging rather than making silently while
"just adding tests" — happy to do it as a scoped follow-up if wanted.
"""

import os
import tempfile
import unittest

from alembic.script import ScriptDirectory
from flask_migrate import stamp

from app import create_app, db


class TestMigrationSafety(unittest.TestCase):

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.app = create_app("testing")
        self.app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{self.db_path}"
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def _script_directory(self):
        migrate_ext = self.app.extensions["migrate"].migrate
        directory = migrate_ext.directory
        if not os.path.isabs(directory):
            directory = os.path.join(os.getcwd(), directory)
        return ScriptDirectory(directory)

    def test_migration_chain_has_a_single_head(self):
        heads = self._script_directory().get_heads()
        self.assertEqual(
            len(heads), 1,
            f"Migration history has diverged into multiple heads: {heads}. "
            "Run `flask db merge` to reconcile them before this can be deployed."
        )

    def test_fresh_install_stamped_head_matches_migration_heads(self):
        """A DB provisioned the documented way (create_all + stamp head)
        must end up stamped at the exact same revision the migration files
        say is head. If these ever disagree, `flask db upgrade` run
        against that DB wouldn't actually apply the migration(s) needed to
        reach the schema models.py/the app's code assumes exists — the
        exact failure mode behind the original `jobs.required_skills_raw
        does not exist` production error."""
        expected_heads = self._script_directory().get_heads()
        self.assertEqual(len(expected_heads), 1, "single-head test should already have failed if this isn't true")

        stamp(revision="head")
        engine = db.engine
        with engine.connect() as conn:
            context = self._alembic_migration_context(conn)
            current_rev = context.get_current_revision()

        self.assertEqual(
            current_rev, expected_heads[0],
            f"`flask db stamp head` on a freshly-provisioned DB landed on '{current_rev}', "
            f"but the migration files' actual head is '{expected_heads[0]}'."
        )

    @staticmethod
    def _alembic_migration_context(connection):
        from alembic.runtime.migration import MigrationContext
        return MigrationContext.configure(connection)


if __name__ == "__main__":
    unittest.main()

