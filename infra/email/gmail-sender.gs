/**
 * Sends the emails of the Immobiliare Taraborrelli app (notices to the agency, "password
 * dimenticata" codes) from the Gmail account that owns this script. Free, 100 recipients
 * a day. Setup: docs/deploy/render.md, section "Email".
 *
 * The services POST {token, to, subject, text, senderName}. The token must match the TOKEN
 * script property (Project Settings -> Script properties), so only they can send.
 */
function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var token = PropertiesService.getScriptProperties().getProperty('TOKEN');
    if (!token || data.token !== token) return answer({ ok: false, error: 'unauthorized' });
    if (!data.to || !data.subject || !data.text) return answer({ ok: false, error: 'invalid' });
    MailApp.sendEmail({
      to: String(data.to),
      subject: String(data.subject),
      body: String(data.text),
      name: String(data.senderName || 'Immobiliare Taraborrelli'),
    });
    return answer({ ok: true });
  } catch (error) {
    return answer({ ok: false, error: 'failed' });
  }
}

function answer(result) {
  return ContentService.createTextOutput(JSON.stringify(result)).setMimeType(
    ContentService.MimeType.JSON,
  );
}

/** Run once from the editor: Google asks for permission to send email from this account. */
function authorize() {
  MailApp.sendEmail(
    Session.getActiveUser().getEmail(),
    'Immobiliare Taraborrelli - prova',
    'Lo script per le email dell\'app funziona.',
  );
}
