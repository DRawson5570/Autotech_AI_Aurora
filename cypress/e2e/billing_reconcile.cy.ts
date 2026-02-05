describe('Admin Billing reconcile flow', () => {
  it('loads pending purchases, triggers reconcile all, shows spinner and results', () => {
    // Stub purchases list to return one pending
    cy.intercept('GET', '/api/v1/billing/admin/purchases*', {
      statusCode: 200,
      body: { items: [{ id: 'p1', user_id: 'u1', tokens: 100, cost: '1.00', status: 'pending' }], total: 1 },
    }).as('listPurchases');

    // Stub reconcile_all endpoint
    cy.intercept('POST', '/api/v1/billing/admin/purchases/reconcile_all*', (req) => {
      req.reply({ statusCode: 200, body: { results: [{ purchase_id: 'p1', action: 'confirmed', reason: 'test' }], count: 1 } });
    }).as('reconcileAll');

    // Stub auth locally: set a token and intercept auth validation so no real registration/login is needed
    // Intercept auth checks (support register/login and app user info)
    // Intercept auth checks (support register/login and app user info) - match any host
    cy.intercept('GET', '**/api/v1/auths*', {
      statusCode: 200,
      body: { id: 'admin', email: 'admin@example.com', role: 'admin' },
    }).as('auth');
    cy.intercept('GET', '**/api/v1/users/me', {
      statusCode: 200,
      body: { id: 'admin', email: 'admin@example.com', role: 'admin' },
    }).as('userInfo');

    // Specific stubs for purchases and reconcile defined below

    // Fallback: catch any other API calls and return a successful empty response to avoid 401s during local tests
    cy.intercept({ url: '**/api/v1/**' }, (req) => {
      req.reply({ statusCode: 200, body: {} });
    }).as('apiCatchAll');

    // Instrument network requests for debugging
    cy.intercept({ url: '/**' }, (req) => {
      console.log('[REQ]', req.method, req.url);
      req.on('response', (res) => {
        console.log('[RES]', res.statusCode, req.url);
      });
      req.continue();
    });

    // Visit the local client-only test route that mounts the Billing component directly (avoid SSR)
    // Get a signed token from the test-only backend helper so SSR can recognize the session
    cy.request('/__test/admin-token').then((res) => {
      const token = res.body?.token;
      if (token) {
        cy.setCookie('token', token);
      }
    });

    cy.visit('/__test/admin-billing', {
      onBeforeLoad(win) {
        win.localStorage.setItem('version', 'test');
        win.__logs = [];
        const origLog = win.console.log.bind(win.console);
        win.console.log = (...args) => {
          win.__logs.push(['log', ...args]);
          origLog(...args);
        };
        win.__errors = [];
        const origErr = win.console.error.bind(win.console);
        win.console.error = (...args) => {
          win.__errors.push(args);
          origErr(...args);
        };
      },
    });

    // Give the app a moment to hydrate

    // Give the app a moment then log body text and captured console logs for debugging via task
    cy.wait(1000);
    cy.window().then((w) => {
      cy.task('log', { event: 'initial_page', body: w.document.body.innerText.slice(0, 4000), logs: w.__logs || [], errors: w.__errors || [] });
    });

    // Wait for admin billing section to be visible, then Load pending (long timeout because app may take time to hydrate)
    cy.contains('Pending Purchases', { timeout: 30000 }).should('be.visible');
    cy.contains('Load Pending', { timeout: 30000 }).should('be.visible').click();
    cy.wait('@listPurchases').then((interception) => {
      cy.task('log', { event: 'listPurchases', response: interception.response });
    });

    // The pending purchase row should be visible
    cy.contains('p1').should('be.visible');
    cy.contains('pending').should('be.visible');

    // Click Reconcile All and assert spinner shows
    cy.contains('Reconcile All').click();
    cy.contains('Reconciling…').should('be.visible');

    // Wait for reconcile request and then assert results visible
    cy.wait('@reconcileAll').then((interception) => {
      cy.task('log', { event: 'reconcileAll', response: interception.response });
    });

    cy.contains('Reconcile Results').should('be.visible');
    cy.contains('p1').should('be.visible');
    cy.contains('confirmed').should('be.visible');

    // Extra debug snapshot of page body text
    cy.window().then((w) => cy.task('log', { event: 'pageBody', body: w.document.body.innerText.slice(0, 8000) }));

    // Ensure the purchases status updates in the table
    cy.get('table').contains('td', 'confirmed').should('exist');
  });
});
