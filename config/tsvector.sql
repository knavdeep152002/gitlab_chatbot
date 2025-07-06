-- 1. Create a function to update the tsvector column
CREATE OR REPLACE FUNCTION documents_tsv_trigger() RETURNS trigger AS $$
BEGIN
  NEW.content_tsv := to_tsvector('english', coalesce(NEW.content, ''));
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

-- 2. Create a trigger to call the function before insert or update
CREATE TRIGGER tsvectorupdate
BEFORE INSERT OR UPDATE ON documents
FOR EACH ROW EXECUTE PROCEDURE documents_tsv_trigger();
