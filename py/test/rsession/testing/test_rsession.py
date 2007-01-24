
""" Tests various aspects of rsession, like ssh hosts setup/teardown
"""

import py
from py.__.test.rsession import report
from py.__.test.rsession.rsession import RSession, parse_directories,\
    session_options, remote_options, parse_directories
from py.__.test.rsession.hostmanage import init_hosts, teardown_hosts,\
     HostInfo
from py.__.test.rsession.testing.test_slave import funcfail_spec,\
    funcpass_spec, funcskip_spec, funcprint_spec, funcprintfail_spec, \
    funcoptioncustom_spec, funcoption_spec

def setup_module(mod):
    mod.pkgdir = py.path.local(py.__file__).dirpath()

def test_setup_non_existing_hosts(): 
    setup_events = []
    hosts = [HostInfo("alskdjalsdkjasldkajlsd")]
    cmd = "init_hosts(setup_events.append, hosts, pkgdir)"
    py.test.raises((py.process.cmdexec.Error, IOError, EOFError), cmd)
    #assert setup_events

def test_getpkdir():
    one = pkgdir.join("initpkg.py")
    two = pkgdir.join("path", "__init__.py")
    p1 = RSession.getpkgdir(one)
    p2 = RSession.getpkgdir(two) 
    assert p1 == p2
    assert p1 == pkgdir 

def test_getpkdir_no_inits():
    tmp = py.test.ensuretemp("getpkdir1")
    fn = tmp.ensure("hello.py")
    assert RSession.getpkgdir(fn) == fn

def test_make_colitems():
    one = pkgdir.join("initpkg.py")
    two = pkgdir.join("path", "__init__.py")

    cols = RSession.make_colitems([one, two], baseon=pkgdir) 
    assert len(cols) == 2
    col_one, col_two = cols
    assert col_one.listnames() == ["py", "initpkg.py"]
    assert col_two.listnames() == ["py", "path", "__init__.py"]

    cols = RSession.make_colitems([one, two], baseon=pkgdir.dirpath()) 
    assert len(cols) == 2
    col_one, col_two = cols
    assert col_one.listnames() == [pkgdir.dirpath().basename, 
                                   "py", "initpkg.py"]
    assert col_two.listnames() == [pkgdir.dirpath().basename, 
                                   "py", "path", "__init__.py"]

def test_example_tryiter():
    events = []
    tmpdir = py.test.ensuretemp("tryitertest")
    tmpdir.ensure("a", "__init__.py")
    tmpdir.ensure("conftest.py").write(py.code.Source("""
        import py
        py.test.skip("Reason")
    """))
    tmpdir.ensure("a", "test_empty.py").write(py.code.Source("""
        def test_empty():
            pass
    """))
    rootcol = py.test.collect.Directory(tmpdir)
    data = list(rootcol.tryiter(reporterror=events.append))
    assert len(events) == 2
    assert str(events[1][0].value) == "Reason"

class TestRSessionRemote: 
    def test_example_distribution_minus_x(self):
        tmpdir = py.test.ensuretemp("example_distribution_minus_x")
        tmpdir.ensure("sub", "conftest.py").write(py.code.Source("""
            disthosts = [%r]
        """ % ('localhost',)))
        tmpdir.ensure("sub", "__init__.py")
        tmpdir.ensure("sub", "test_one.py").write(py.code.Source("""
            def test_1(): 
                pass
            def test_x():
                import py
                py.test.skip("aaa")
            def test_2():
                assert 0
            def test_3():
                raise ValueError(23)
            def test_4(someargs):
                pass
        """))
        args = [str(tmpdir.join("sub")), "-x"]
        config = py.test.config._reparse(args)
        rsession = RSession(config)
        allevents = []
        rsession.main(reporter=allevents.append)
        testevents = [x for x in allevents 
                        if isinstance(x, report.ReceivedItemOutcome)]
        assert len(testevents) == 3
        assert rsession.checkfun()

    def test_example_distribution(self):
        subdir = "sub_example_dist"
        tmpdir = py.test.ensuretemp("example_distribution")
        tmpdir.ensure(subdir, "conftest.py").write(py.code.Source("""
            disthosts = [%r]
            distrsync_roots = ["%s"]
        """ % ('localhost', subdir)))
        tmpdir.ensure(subdir, "__init__.py")
        tmpdir.ensure(subdir, "test_one.py").write(py.code.Source("""
            def test_1(): 
                pass
            def test_2():
                assert 0
            def test_3():
                raise ValueError(23)
            def test_4(someargs):
                pass
            def test_5():
                assert __file__ != '%s'
        """ % str(tmpdir.join(subdir))))
        args = [str(tmpdir.join(subdir))]
        config = py.test.config._reparse(args)
        rsession = RSession(config, optimise_localhost=False)
        allevents = []
        rsession.main(reporter=allevents.append) 
        testevents = [x for x in allevents 
                        if isinstance(x, report.ReceivedItemOutcome)]
        assert len(testevents)
        passevents = [i for i in testevents if i.outcome.passed]
        failevents = [i for i in testevents if i.outcome.excinfo]
        skippedevents = [i for i in testevents if i.outcome.skipped]
        assert len(testevents) == 5
        assert len(passevents) == 2
        assert len(failevents) == 3
        tb = failevents[0].outcome.excinfo.traceback
        assert tb[0].path.find("test_one") != -1
        assert tb[0].source.find("test_2") != -1
        assert failevents[0].outcome.excinfo.typename == 'AssertionError'
        tb = failevents[1].outcome.excinfo.traceback
        assert tb[0].path.find("test_one") != -1
        assert tb[0].source.find("test_3") != -1
        assert failevents[1].outcome.excinfo.typename == 'ValueError'
        assert failevents[1].outcome.excinfo.value == '23'
        tb = failevents[2].outcome.excinfo.traceback
        assert failevents[2].outcome.excinfo.typename == 'TypeError'
        assert tb[0].path.find("executor") != -1
        assert tb[0].source.find("execute") != -1
        
    def test_setup_teardown_ssh(self):
        hosts = [HostInfo('localhost')]
        parse_directories(hosts)
        setup_events = []
        teardown_events = []
        
        config = py.test.config._reparse([])
        session_options.bind_config(config)
        nodes = init_hosts(setup_events.append, hosts, pkgdir,
            rsync_roots=["py"], optimise_localhost=False, remote_options=remote_options.d)
        teardown_hosts(teardown_events.append, 
                       [node.channel for node in nodes], nodes)
        
        count_rsyn_calls = [i for i in setup_events 
                if isinstance(i, report.HostRSyncing)]
        assert len(count_rsyn_calls) == len([i for i in hosts])
        count_ready_calls = [i for i in setup_events 
                if isinstance(i, report.HostReady)]
        assert len(count_ready_calls) == len([i for i in hosts])
        
        # same for teardown events
        teardown_wait_starts = [i for i in teardown_events 
                                    if isinstance(i, report.CallStart)]
        teardown_wait_ends = [i for i in teardown_events 
                                    if isinstance(i, report.CallFinish)]
        assert len(teardown_wait_starts) == len(hosts)
        assert len(teardown_wait_ends) == len(hosts)

    def test_setup_teardown_run_ssh(self):
        hosts = [HostInfo('localhost')]
        parse_directories(hosts)
        allevents = []
        
        config = py.test.config._reparse([])
        session_options.bind_config(config)
        nodes = init_hosts(allevents.append, hosts, pkgdir,
            rsync_roots=["py"], optimise_localhost=False, remote_options=remote_options.d)
        
        from py.__.test.rsession.testing.test_executor \
            import ItemTestPassing, ItemTestFailing, ItemTestSkipping
        
        rootcol = py.test.collect.Directory(pkgdir.dirpath())
        itempass = rootcol.getitembynames(funcpass_spec)
        itemfail = rootcol.getitembynames(funcfail_spec)
        itemskip = rootcol.getitembynames(funcskip_spec)
        itemprint = rootcol.getitembynames(funcprint_spec)

        # actually run some tests
        for node in nodes:
            node.send(itempass)
            node.send(itemfail)
            node.send(itemskip)
            node.send(itemprint)

        teardown_hosts(allevents.append, [node.channel for node in nodes], nodes)

        events = [i for i in allevents 
                        if isinstance(i, report.ReceivedItemOutcome)]
        passed = [i for i in events 
                        if i.outcome.passed]
        skipped = [i for i in events 
                        if i.outcome.skipped]
        assert len(passed) == 2 * len(nodes)
        assert len(skipped) == len(nodes)
        assert len(events) == 4 * len(nodes)
        # one of passed for each node has non-empty stdout
        passed_stdout = [i for i in passed if i.outcome.stdout.find('samfing') != -1]
        assert len(passed_stdout) == len(nodes), passed

    def test_config_pass(self):
        """ Tests options object passing master -> server
        """
        allevents = []
        hosts = [HostInfo('localhost')]
        parse_directories(hosts)
        config = py.test.config._reparse([])
        session_options.bind_config(config)
        d = remote_options.d.copy()
        d['custom'] = 'custom'
        nodes = init_hosts(allevents.append, hosts, pkgdir, 
            rsync_roots=["py"], remote_options=d,
            optimise_localhost=False)
        
        rootcol = py.test.collect.Directory(pkgdir.dirpath())
        itempass = rootcol.getitembynames(funcoption_spec)
        itempassaswell = rootcol.getitembynames(funcoptioncustom_spec)
        
        for node in nodes:
            node.send(itempass)
            node.send(itempassaswell)
        
        teardown_hosts(allevents.append, [node.channel for node in nodes], nodes)
        events = [i for i in allevents 
                        if isinstance(i, report.ReceivedItemOutcome)]
        passed = [i for i in events 
                        if i.outcome.passed]
        skipped = [i for i in events 
                        if i.outcome.skipped]
        assert len(passed) == 2 * len(nodes)
        assert len(skipped) == 0
        assert len(events) == len(passed)
    
    def test_nice_level(self):
        """ Tests if nice level behaviour is ok
        """
        allevents = []
        hosts = [HostInfo('localhost')]
        parse_directories(hosts)
        tmpdir = py.test.ensuretemp("nice")
        tmpdir.ensure("__init__.py")
        tmpdir.ensure("conftest.py").write("""disthosts = ['localhost']""")
        tmpdir.ensure("test_one.py").write("""def test_nice():
            import os
            assert os.nice(0) == 10
        """)
        
        config = py.test.config._reparse([tmpdir])
        config.option.nice_level = 10
        rsession = RSession(config)
        allevents = []
        rsession.main(reporter=allevents.append) 
        testevents = [x for x in allevents 
                        if isinstance(x, report.ReceivedItemOutcome)]
        passevents = [x for x in testevents if x.outcome.passed]
        assert len(passevents) == 1
    
class XxxTestDirectories(object):
    # need complete rewrite, and unsure if it makes sense at all
    def test_simple_parse(self):
        sshhosts = [HostInfo(i) for i in ['h1', 'h2', 'h3']]
        parse_directories(sshhosts)
    
    def test_sophisticated_parse(self):
        sshhosts = ['a@h1:/tmp', 'h2:tmp', 'h3']
        dirs = parse_directories(sshhosts)
        assert py.builtin.sorted(
            dirs.values()) == ['/tmp', 'pytestcache', 'tmp']
    
    def test_parse_multiple_hosts(self):
        hosts = ['h1', 'h1', 'h1:/tmp']
        dirs = parse_directories(hosts)
        assert dirs == {(0, 'h1'): 'pytestcache', (1, 'h1'): 'pytestcache', 
            (2, 'h1'):'/tmp'}

class TestInithosts(object):
    def test_inithosts(self):
        testevents = []
        hostnames = ['h1:/tmp', 'h1:/tmp', 'h1:/other', 'h2', 'h2:home']
        hosts = [HostInfo(i) for i in hostnames]
        parse_directories(hosts)
        init_hosts(testevents.append, hosts, pkgdir, do_sync=False)
        events = [i for i in testevents if isinstance(i, report.HostRSyncing)]
        assert len(events) == 4
        assert events[0].host.hostname == 'h1'
        assert events[0].host.relpath == '/tmp-h1'
        assert events[1].host.hostname == 'h1'
        assert events[1].host.relpath == '/other-h1'
        assert events[2].host.hostname == 'h2'
        assert events[2].host.relpath == 'pytestcache-h2'
        assert events[3].host.hostname == 'h2'
        assert events[3].host.relpath == 'home-h2'
        
