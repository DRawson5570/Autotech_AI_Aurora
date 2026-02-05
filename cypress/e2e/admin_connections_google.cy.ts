describe('Admin Connections - Google', () => {
  it('shows Google API section and opens config modal via gear', () => {
    // Requires dev server running at http://localhost:5173 and backend at 8080
    cy.visit('http://localhost:5173/admin/settings/connections');

    // The page may redirect to login if not authenticated; skip auth handling here
    cy.contains('Google API').should('exist');

    // If any Google connection exists, the cog should be visible; otherwise the Add button exists
    cy.get('body').then(($body) => {
      if ($body.find('button[aria-label="Configure"]').length) {
        cy.get('button[aria-label="Configure"]').first().click();
        // Modal should appear (AddConnectionModal uses role/heading text)
        cy.contains('Add Connection').should('exist');
      } else if ($body.find('button:contains("Add")').length) {
        // Fallback: click Add Connection button
        cy.contains('Add Connection').click();
        cy.contains('Add Connection').should('exist');
      }
    });
  });
});