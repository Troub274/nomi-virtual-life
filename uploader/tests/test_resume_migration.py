"""Offline crash/restart regressions for the Mary 1:499 migration."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_uploader import u

OLD = '41e3bb66-4ae4-420d-9251-a68083eda60a'
NEW = 'fresh-room'

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cp = self.root / 'checkpoint.jsonl'
        self.messages = [dict(text=str(i), kind='prompt' if i in (499, 501) else 'content')
                         for i in range(1, 502)]
        self.args = SimpleNamespace(checkpoint=str(self.cp), completion=str(self.root/'completed.json'),
            replies=str(self.root/'replies.txt'), resume=True, dry_run=False, room=None,
            files=['fixture'], passes=1, user='', chunk_bytes=750, process_every=0,
            date_format='US', delay=0, new_room_on_resume=True, abandon_reply=['1:499'])
        u.record(self.cp, dict(event='start', run_id='mary-run', nomi_uuid='mary', nomi_name='Mary',
            room_uuid=OLD, year=2026, order='US', files=['fixture'], passes=1,
            messages_per_pass=501, manifest=u.digest(self.messages)))
        for i in range(1, 500):
            u.record(self.cp, dict(event='confirmed', index=i,
                kind=self.messages[i-1]['kind'], **{'pass':1}))
        u.record(self.cp, dict(event='reply_attempt', index=499, room_uuid=OLD, **{'pass':1}))
        self.prefix = self.cp.read_bytes()
        self.calls = []
        self.rooms = []

    def api(self, path, method='GET', payload=None):
        self.calls.append((path, payload))
        if path == '/rooms':
            self.rooms.append(dict(uuid=NEW, name=payload['name'], nomiUuids=['mary']))
            return 200, {'uuid':NEW}
        if path.endswith('/chat/request'):
            return 200, {'replyMessage':{'text':'reflection'}}
        return 200, {'uuid':'sent'}

    def run_upload(self, record=None, wait=None):
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(u, 'plan_text', return_value=self.messages))
            stack.enter_context(patch.object(u.legacy, 'api_request', side_effect=self.api))
            stack.enter_context(patch.object(u.legacy, 'list_rooms', side_effect=lambda:self.rooms))
            stack.enter_context(patch.object(u.legacy, 'wait_for_room', side_effect=wait))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            if record: stack.enter_context(patch.object(u, 'record', side_effect=record))
            u.upload(self.args)

    def rows(self): return u.records(self.cp)
    def plain_resume(self):
        self.args.new_room_on_resume=False
        self.args.abandon_reply=[]

    def test_continues_at_500_in_fresh_room_and_repeated_flags_are_idempotent(self):
        self.run_upload()
        self.assertTrue(self.cp.read_bytes().startswith(self.prefix))
        self.assertEqual([p['messageText'] for path,p in self.calls if path.endswith('/chat')], ['500','501'])
        self.assertTrue(all(path.startswith('/rooms/'+NEW) for path,p in self.calls if path!='/rooms'))
        self.assertEqual(len([e for e in self.rows() if e['event']=='reply_abandoned']),1)
        self.assertEqual(len([e for e in self.rows() if e['event']=='room_migrated']),1)
        self.assertEqual(self.rows()[0]['room_uuid'],OLD)
        self.calls.clear()
        self.run_upload()
        self.assertEqual(self.calls,[])
        self.assertEqual(u.active_room_ids(self.root),set())
        Path(self.args.completion).unlink()
        self.assertEqual(u.active_room_ids(self.root),{OLD,NEW})

    def test_restart_at_each_durable_boundary(self):
        real=u.record
        for boundary in ('reply_abandoned','room_migration_intent','room_migrated','attempt','confirmed'):
            with self.subTest(boundary=boundary):
                self.cp.write_bytes(self.prefix); self.calls.clear(); self.rooms.clear()
                self.args.new_room_on_resume=True; self.args.abandon_reply=['1:499']
                def interrupted(path,event):
                    if event['event']==boundary:
                        if boundary=='reply_abandoned': real(path,event)
                        raise KeyboardInterrupt()
                    real(path,event)
                with self.assertRaises(KeyboardInterrupt): self.run_upload(interrupted)
                self.plain_resume()
                if boundary=='confirmed':
                    with self.assertRaisesRegex(RuntimeError,'Uncertain send'): self.run_upload()
                    self.assertEqual(len(self.rooms),1)
                    continue
                self.run_upload()
                self.assertEqual(len(self.rooms),1)
                self.assertEqual(len([e for e in self.rows() if e['event']=='room_migrated']),1)
                self.args.new_room_on_resume=True; self.args.abandon_reply=['1:499']

    def test_uncertain_create_does_not_repeat_post_when_no_room_visible(self):
        real=u.record
        def stop(path,event):
            real(path,event)
            if event['event']=='room_migration_intent': raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.run_upload(stop)
        self.plain_resume()
        with self.assertRaisesRegex(RuntimeError,'no automatic create retry'): self.run_upload()
        self.assertEqual(self.calls,[])

    def test_pending_intent_protects_created_room_before_migration_event(self):
        real=u.record
        def stop(path,event):
            if event['event']=='room_migrated': raise KeyboardInterrupt()
            real(path,event)
        with self.assertRaises(KeyboardInterrupt): self.run_upload(stop)
        with patch.object(u.legacy,'list_rooms',return_value=self.rooms):
            self.assertEqual(u.active_room_ids(self.root),{OLD,NEW})
        self.plain_resume(); self.run_upload()
        self.assertEqual(len(self.rooms),1)

    def test_reject_invalid_abandonment_before_checkpoint_mutation_or_api(self):
        for token in ('bad','0:499','1:0','1:498','2:499','1:502'):
            with self.subTest(token=token):
                self.args.abandon_reply=[token]
                with self.assertRaises(ValueError): self.run_upload()
                self.assertEqual(self.calls,[])
                self.assertEqual(self.cp.read_bytes(),self.prefix)

    def test_unconfirmed_prompt_and_other_uncertain_send_block_migration(self):
        u.record(self.cp,dict(event='attempt',index=500,**{'pass':1}))
        with self.assertRaisesRegex(ValueError,'uncertain sends'): self.run_upload()
        self.assertEqual(self.calls,[])
        self.assertFalse(any(e['event']=='reply_abandoned' for e in self.rows()))

    def test_flags_require_resume_and_disallow_conflicting_options(self):
        for field,value in [('resume',False),('dry_run',True),('room',OLD),
                            ('recover_uncertain_reply',['1:499']),('retry_uncertain_send',['1:500'])]:
            with self.subTest(field=field):
                original=getattr(self.args,field,None)
                setattr(self.args,field,value)
                with self.assertRaises(ValueError): self.run_upload()
                setattr(self.args,field,original)
                self.assertEqual(self.calls,[])

    def test_manifest_change_creates_no_room(self):
        self.messages[0]['text']='changed'
        with self.assertRaisesRegex(ValueError,'Manifest changed'): self.run_upload()
        self.assertEqual(self.calls,[])

    def test_reconciliation_rejects_duplicate_matches_and_wrong_nomi(self):
        real=u.record
        def stop(path,event):
            if event['event']=='room_migrated': raise KeyboardInterrupt()
            real(path,event)
        with self.assertRaises(KeyboardInterrupt): self.run_upload(stop)
        self.rooms.append(dict(self.rooms[0],uuid='duplicate'))
        with self.assertRaisesRegex(RuntimeError,'uncertain'): self.run_upload()
        self.rooms.pop(); self.rooms[0]['nomiUuids']=['other']
        with self.assertRaisesRegex(ValueError,'not associated'): self.run_upload()
        self.assertEqual(len([c for c in self.calls if c[0]=='/rooms']),1)

    def test_concurrent_upload_cannot_create_duplicate_room(self):
        api=self.api
        def concurrent(path,method='GET',payload=None):
            if path=='/rooms':
                with self.assertRaisesRegex(RuntimeError,'in use'): u.upload(self.args)
            return api(path,method,payload)
        with patch.object(u.legacy,'api_request',side_effect=concurrent):
            # run_upload installs its own API mock, so call through a wrapper.
            original=self.api; self.api=concurrent
            try: self.run_upload()
            finally: self.api=original
        self.assertEqual(len(self.rooms),1)

    def test_wait_interruption_resumes_same_destination(self):
        with self.assertRaises(KeyboardInterrupt): self.run_upload(wait=KeyboardInterrupt())
        self.assertTrue(any(e['event']=='room_migrated' for e in self.rows()))
        self.assertFalse(any(path.endswith('/chat') for path,p in self.calls))
        self.plain_resume(); self.run_upload()
        self.assertEqual(len(self.rooms),1)

    def test_torn_checkpoint_is_preserved_and_both_rooms_stay_protected(self):
        self.run_upload()
        with self.cp.open('ab') as out: out.write(b'{"event":"partial')
        before=self.cp.read_bytes()
        self.plain_resume()
        with self.assertRaisesRegex(ValueError,'Incomplete checkpoint'): self.run_upload()
        self.assertEqual(self.cp.read_bytes(),before)
        self.assertEqual(u.active_room_ids(self.root),{OLD,NEW})

    def test_completion_requires_abandonment_audit(self):
        self.run_upload()
        marker=Path(self.args.completion)
        data=json.loads(marker.read_text())
        self.assertEqual(data['abandoned_replies'],[[1,499]])
        data.pop('abandoned_replies')
        marker.write_text(json.dumps(data))
        self.assertEqual(u.active_room_ids(self.root),{OLD,NEW})

    def test_already_committed_reply_cannot_be_abandoned(self):
        u.record(self.cp,dict(event='reply_committed',index=499,**{'pass':1}))
        with self.assertRaisesRegex(ValueError,'No pending confirmed'): self.run_upload()
        self.assertEqual(self.calls,[])

    def test_later_pending_reply_cannot_be_abandoned_without_new_migration(self):
        self.run_upload()
        self.args.abandon_reply=['1:501']
        with self.assertRaises(ValueError): self.run_upload()
        self.assertEqual(len(self.rooms),1)

    def test_utility_migration_flags_rejected(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            u.main(['--utility','--resume','--new-room-on-resume','--abandon-reply','1:499'])

    def test_lost_create_response_reconciles_without_duplicate(self):
        api=self.api
        def lost(path,method='GET',payload=None):
            result=api(path,method,payload)
            if path=='/rooms': raise KeyboardInterrupt()
            return result
        self.api=lost
        with self.assertRaises(KeyboardInterrupt): self.run_upload()
        self.api=api
        self.plain_resume(); self.run_upload()
        self.assertEqual(len(self.rooms),1)
        self.assertEqual(len([c for c in self.calls if c[0]=='/rooms']),1)

    def test_missing_earlier_confirmation_blocks_migration(self):
        rows=[e for e in self.rows() if e.get('index')!=42]
        self.cp.write_bytes(b'')
        for e in rows: u.record(self.cp,e)
        with self.assertRaisesRegex(ValueError,'contiguous confirmed prefix'): self.run_upload()
        self.assertEqual(self.calls,[])

    def test_partial_multi_abandonment_cannot_move_other_pending_reply(self):
        self.messages[497]['kind']='prompt'
        rows=self.rows(); rows[0]['manifest']=u.digest(self.messages)
        rows[498]['kind']='prompt'
        self.cp.write_bytes(b'')
        for e in rows: u.record(self.cp,e)
        u.record(self.cp,dict(event='reply_attempt',index=498,**{'pass':1}))
        u.record(self.cp,dict(event='reply_uncertain',index=498,http_status=500,
                              api_response={'type':'NoReply'},**{'pass':1}))
        u.record(self.cp,dict(event='reply_abandoned',index=499,room_uuid=OLD,**{'pass':1}))
        self.plain_resume()
        with self.assertRaisesRegex(ValueError,'all pending replies'): self.run_upload()
        self.assertEqual(self.calls,[])
