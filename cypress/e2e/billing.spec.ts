describe('Billing portal', () => {
  it('calls backend and redirects to Stripe', () => {
    const portalUrl = 'https://billing.stripe.com/test-session'

    // Stub the API call
    cy.intercept('POST', '/api/v1/billing/portal', {
      statusCode: 200,
      body: { url: portalUrl },
    }).as('createPortal')

    // Visit account settings (adjust path if app mounts routes differently)
    cy.visit('/')

    // Open settings UI and click Manage Billing
    // Adjust selectors if needed depending on the app
    cy.get('[id="tab-account"]').should('exist')
    cy.get('[id="tab-account"]').within(() => {
      cy.contains('Manage Billing').click()
    })

    // Ensure API was called and the browser was redirected
    cy.wait('@createPortal')
    cy.location('href').should('equal', portalUrl)
  })
})